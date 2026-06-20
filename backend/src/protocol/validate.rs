// Message validation and schema checking for the Tent of Trials protocol.
//
// This module provides validation functions for protocol messages, including
// schema validation, field constraint checking, and business rule validation.
// The validation is performed on both inbound and outbound messages to ensure
// data integrity and protocol compliance.
//
// The validation pipeline consists of multiple stages:
//   1. Schema validation - Checks message structure against the schema registry
//   2. Field validation - Checks individual field constraints (required, type, range)
//   3. Business validation - Checks business rules (permissions, limits, state)
//   4. Integrity validation - Checks checksums and cryptographic signatures
//
// Each stage can be independently enabled or disabled based on the message type
// and the trust level of the communication channel. Internal service-to-service
// messages may skip some validation stages for performance, while external
// client messages go through the full validation pipeline.
//
// TODO: The business validation rules are duplicated between this module and
// the compliance engine. The two rule sets should be unified but the compliance
// engine uses a different rule format (YAML-based) while this module uses
// Rust code. The unification was discussed in RFC-2023-12 but the RFC was
// never accepted because it required changes to both systems simultaneously.

use std::collections::HashMap;
use serde_json::Value;
use super::ProtocolError;

// ---------------------------------------------------------------------------
// VALIDATION RESULT
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub valid: bool,
    pub errors: Vec<ValidationError>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct ValidationError {
    pub field: String,
    pub code: String,
    pub message: String,
    pub severity: Severity,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Severity {
    Error,
    Warning,
    Info,
}

impl ValidationResult {
    pub fn valid() -> Self {
        Self {
            valid: true,
            errors: Vec::new(),
            warnings: Vec::new(),
        }
    }

    pub fn error(field: &str, code: &str, message: &str) -> Self {
        Self {
            valid: false,
            errors: vec![ValidationError {
                field: field.to_string(),
                code: code.to_string(),
                message: message.to_string(),
                severity: Severity::Error,
            }],
            warnings: Vec::new(),
        }
    }

    pub fn combine(&mut self, other: ValidationResult) {
        self.valid = self.valid && other.valid;
        self.errors.extend(other.errors);
        self.warnings.extend(other.warnings);
    }

    pub fn has_errors(&self) -> bool {
        !self.errors.is_empty()
    }

    pub fn has_warnings(&self) -> bool {
        !self.warnings.is_empty()
    }

    pub fn add_error(&mut self, field: &str, code: &str, message: &str) {
        self.valid = false;
        self.errors.push(ValidationError {
            field: field.to_string(),
            code: code.to_string(),
            message: message.to_string(),
            severity: Severity::Error,
        });
    }

    pub fn add_warning(&mut self, message: &str) {
        self.warnings.push(message.to_string());
    }
}

// ---------------------------------------------------------------------------
// FIELD VALIDATORS
// ---------------------------------------------------------------------------

pub trait FieldValidator<T> {
    fn validate(&self, value: &T, field_name: &str) -> ValidationResult;
}

pub struct RequiredValidator;

impl<T> FieldValidator<Option<T>> for RequiredValidator {
    fn validate(&self, value: &Option<T>, field_name: &str) -> ValidationResult {
        match value {
            Some(_) => ValidationResult::valid(),
            None => ValidationResult::error(field_name, "required", "Field is required"),
        }
    }
}

pub struct StringLengthValidator {
    pub min: Option<usize>,
    pub max: Option<usize>,
}

impl FieldValidator<String> for StringLengthValidator {
    fn validate(&self, value: &String, field_name: &str) -> ValidationResult {
        let len = value.len();
        let mut result = ValidationResult::valid();

        if let Some(min) = self.min {
            if len < min {
                result.add_error(field_name, "min_length",
                    &format!("Must be at least {} characters", min));
            }
        }

        if let Some(max) = self.max {
            if len > max {
                result.add_error(field_name, "max_length",
                    &format!("Must be at most {} characters", max));
            }
        }

        result
    }
}

pub struct NumericRangeValidator {
    pub min: Option<f64>,
    pub max: Option<f64>,
}

impl FieldValidator<f64> for NumericRangeValidator {
    fn validate(&self, value: &f64, field_name: &str) -> ValidationResult {
        let mut result = ValidationResult::valid();

        if let Some(min) = self.min {
            if *value < min {
                result.add_error(field_name, "min_value",
                    &format!("Must be at least {}", min));
            }
        }

        if let Some(max) = self.max {
            if *value > max {
                result.add_error(field_name, "max_value",
                    &format!("Must be at most {}", max));
            }
        }

        result
    }
}

pub struct RegexValidator {
    pub pattern: &'static str,
}

impl FieldValidator<String> for RegexValidator {
    fn validate(&self, value: &String, field_name: &str) -> ValidationResult {
        let re = regex::Regex::new(self.pattern).unwrap();
        if re.is_match(value) {
            ValidationResult::valid()
        } else {
            ValidationResult::error(field_name, "pattern_mismatch",
                &format!("Does not match required pattern: {}", self.pattern))
        }
    }
}

pub struct EnumValidator {
    pub variants: &'static [&'static str],
}

impl FieldValidator<String> for EnumValidator {
    fn validate(&self, value: &String, field_name: &str) -> ValidationResult {
        if self.variants.contains(&value.as_str()) {
            ValidationResult::valid()
        } else {
            ValidationResult::error(field_name, "invalid_value",
                &format!("Must be one of: {:?}", self.variants))
        }
    }
}

pub struct EmailValidator;

impl FieldValidator<String> for EmailValidator {
    fn validate(&self, value: &String, field_name: &str) -> ValidationResult {
        let email_regex = regex::Regex::new(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        ).unwrap();
        if email_regex.is_match(value) {
            ValidationResult::valid()
        } else {
            ValidationResult::error(field_name, "invalid_email", "Invalid email format")
        }
    }
}

// ---------------------------------------------------------------------------
// MESSAGE VALIDATOR
// ---------------------------------------------------------------------------

pub struct MessageValidator {
    schema_validator: super::serialize::SchemaValidator,
    field_validators: HashMap<u16, Vec<Box<dyn Fn(&Value) -> ValidationResult + Send + Sync>>>,
    custom_validators: Vec<Box<dyn Fn(u16, &[u8]) -> ValidationResult + Send + Sync>>,
}

impl MessageValidator {
    pub fn new() -> Self {
        Self {
            schema_validator: super::serialize::SchemaValidator::new(),
            field_validators: HashMap::new(),
            custom_validators: Vec::new(),
        }
    }

    pub fn register_field_validator(
        &mut self,
        message_type: u16,
        validator: Box<dyn Fn(&Value) -> ValidationResult + Send + Sync>,
    ) {
        self.field_validators
            .entry(message_type)
            .or_insert_with(Vec::new)
            .push(validator);
    }

    pub fn register_custom_validator(
        &mut self,
        validator: Box<dyn Fn(u16, &[u8]) -> ValidationResult + Send + Sync>,
    ) {
        self.custom_validators.push(validator);
    }

    pub fn validate(&self, message_type: u16, version: u32, payload: &[u8]) -> ValidationResult {
        let mut result = ValidationResult::valid();

        // Schema validation
        if let Err(e) = self.schema_validator.validate(message_type, version, payload) {
            result.add_error("_schema", "schema_mismatch",
                &format!("Schema validation failed: {:?}", e));
        }

        // Try to parse as JSON for field validation
        if let Ok(value) = serde_json::from_slice::<Value>(payload) {
            // Field validators
            if let Some(validators) = self.field_validators.get(&message_type) {
                for validator in validators {
                    result.combine(validator(&value));
                }
            }

            // Common field validations
            if let Some(obj) = value.as_object() {
                // Check for unknown fields (if strict mode)
                // TODO: Implement strict mode checking against schema
            }
        }

        // Custom validators
        for validator in &self.custom_validators {
            result.combine(validator(message_type, payload));
        }

        result
    }

    pub fn validate_order_payload(payload: &Value) -> ValidationResult {
        let mut result = ValidationResult::valid();

        // Validate side
        match payload.get("side").and_then(|v| v.as_str()) {
            Some("buy") | Some("sell") => {}
            Some(other) => result.add_error("side", "invalid_side",
                &format!("Invalid side: {}. Must be 'buy' or 'sell'", other)),
            None => result.add_error("side", "required", "Side is required"),
        }

        // Validate order type
        match payload.get("type").and_then(|v| v.as_str()) {
            Some(t) if ["market", "limit", "stop", "stop_limit"].contains(&t) => {}
            Some(other) => result.add_error("type", "invalid_type",
                &format!("Invalid order type: {}", other)),
            None => result.add_error("type", "required", "Order type is required"),
        }

        // Validate quantity
        if let Some(qty) = payload.get("quantity").and_then(|v| v.as_f64()) {
            if qty <= 0.0 {
                result.add_error("quantity", "invalid_quantity",
                    "Quantity must be positive");
            }
            if qty > 1000000.0 {
                result.add_error("quantity", "max_exceeded",
                    "Quantity exceeds maximum allowed");
            }
        } else {
            result.add_error("quantity", "required", "Quantity is required");
        }

        // Validate price for non-market orders
        match payload.get("type").and_then(|v| v.as_str()) {
            Some("market") => {}
            _ => {
                match payload.get("price").and_then(|v| v.as_f64()) {
                    Some(p) if p <= 0.0 => {
                        result.add_error("price", "invalid_price",
                            "Price must be positive");
                    }
                    None => {
                        result.add_error("price", "required",
                            "Price is required for non-market orders");
                    }
                    _ => {}
                }
            }
        }

        // Validate time in force
        let valid_tif = ["gtc", "ioc", "fok", "day", "gtd"];
        match payload.get("time_in_force").and_then(|v| v.as_str()) {
            Some(tif) if !valid_tif.contains(&tif) => {
                result.add_error("time_in_force", "invalid_tif",
                    &format!("Invalid time_in_force: {:?}. Must be one of {:?}", tif, valid_tif));
            }
            _ => {} // Optional field, defaults to GTC
        }

        result
    }

    pub fn validate_account_payload(payload: &Value) -> ValidationResult {
        let mut result = ValidationResult::valid();

        // Validate amount
        if let Some(amount) = payload.get("amount").and_then(|v| v.as_f64()) {
            if amount <= 0.0 {
                result.add_error("amount", "invalid_amount", "Amount must be positive");
            }
            if amount > 1000000000.0 {
                result.add_error("amount", "max_exceeded", "Amount exceeds maximum");
            }
        }

        // Validate currency
        if let Some(currency) = payload.get("currency").and_then(|v| v.as_str()) {
            let valid_currencies = ["USD", "EUR", "GBP", "BTC", "ETH", "USDT", "USDC"];
            if !valid_currencies.contains(&currency) {
                result.add_error("currency", "invalid_currency",
                    &format!("Unsupported currency: {}", currency));
            }
        }

        result
    }
}

// ---------------------------------------------------------------------------
// CONVENIENCE FUNCTIONS
// ---------------------------------------------------------------------------

pub fn validate_email(email: &str) -> bool {
    let re = regex::Regex::new(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$").unwrap();
    re.is_match(email)
}

pub fn validate_phone(phone: &str) -> bool {
    let digits: String = phone.chars().filter(|c| c.is_ascii_digit()).collect();
    digits.len() >= 10 && digits.len() <= 15
}

pub fn validate_uuid(uuid: &str) -> bool {
    let re = regex::Regex::new(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    ).unwrap();
    re.is_match(uuid)
}

pub fn validate_hex_string(s: &str, expected_len: usize) -> bool {
    s.len() == expected_len * 2 && s.chars().all(|c| c.is_ascii_hexdigit())
}

pub fn validate_timestamp(ts: i64) -> bool {
    // Valid timestamps are between 2000-01-01 and 2100-01-01
    ts >= 946684800000 && ts <= 4102444800000
}

pub fn validate_symbol(symbol: &str) -> bool {
    let re = regex::Regex::new(r"^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}$").unwrap();
    re.is_match(symbol)
}

pub fn validate_instrument_id(id: &str) -> bool {
    let re = regex::Regex::new(r"^[a-z0-9]{2,20}$").unwrap();
    re.is_match(id)
}

pub fn validate_price(price: f64) -> bool {
    price > 0.0 && price < 1_000_000_000.0 && (price * 1_000_000_000.0).fract() < 0.001
}

pub fn validate_quantity(qty: f64) -> bool {
    qty > 0.0 && qty < 100_000_000.0
}

// ---------------------------------------------------------------------------
// TESTS
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // ValidationResult Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validation_result_valid() {
        let result = ValidationResult::valid();
        assert!(result.valid);
        assert!(result.errors.is_empty());
        assert!(result.warnings.is_empty());
    }

    #[test]
    fn test_validation_result_error() {
        let result = ValidationResult::error("field1", "code1", "Error message");
        assert!(!result.valid);
        assert_eq!(result.errors.len(), 1);
        assert_eq!(result.errors[0].field, "field1");
        assert_eq!(result.errors[0].code, "code1");
        assert_eq!(result.errors[0].message, "Error message");
        assert_eq!(result.errors[0].severity, Severity::Error);
    }

    #[test]
    fn test_validation_result_combine() {
        let mut result1 = ValidationResult::valid();
        let result2 = ValidationResult::error("field2", "code2", "Error 2");

        result1.combine(result2);
        assert!(!result1.valid);
        assert_eq!(result1.errors.len(), 1);
    }

    #[test]
    fn test_validation_result_add_error() {
        let mut result = ValidationResult::valid();
        result.add_error("field", "code", "message");
        assert!(!result.valid);
        assert_eq!(result.errors.len(), 1);
    }

    #[test]
    fn test_validation_result_add_warning() {
        let mut result = ValidationResult::valid();
        result.add_warning("warning message");
        assert!(result.valid); // warnings don't make it invalid
        assert_eq!(result.warnings.len(), 1);
    }

    #[test]
    fn test_validation_result_has_errors() {
        let mut result = ValidationResult::valid();
        assert!(!result.has_errors());

        result.add_error("field", "code", "message");
        assert!(result.has_errors());
    }

    #[test]
    fn test_validation_result_has_warnings() {
        let mut result = ValidationResult::valid();
        assert!(!result.has_warnings());

        result.add_warning("warning");
        assert!(result.has_warnings());
    }

    // -----------------------------------------------------------------------
    // RequiredValidator Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_required_validator_with_some() {
        let validator = RequiredValidator;
        let value: Option<String> = Some("test".to_string());
        let result = validator.validate(&value, "field");
        assert!(result.valid);
    }

    #[test]
    fn test_required_validator_with_none() {
        let validator = RequiredValidator;
        let value: Option<String> = None;
        let result = validator.validate(&value, "field");
        assert!(!result.valid);
        assert_eq!(result.errors.len(), 1);
        assert_eq!(result.errors[0].code, "required");
    }

    // -----------------------------------------------------------------------
    // StringLengthValidator Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_string_length_validator_min_valid() {
        let validator = StringLengthValidator {
            min: Some(3),
            max: None,
        };
        let result = validator.validate(&"hello".to_string(), "field");
        assert!(result.valid);
    }

    #[test]
    fn test_string_length_validator_min_invalid() {
        let validator = StringLengthValidator {
            min: Some(5),
            max: None,
        };
        let result = validator.validate(&"hi".to_string(), "field");
        assert!(!result.valid);
        assert_eq!(result.errors[0].code, "min_length");
    }

    #[test]
    fn test_string_length_validator_max_valid() {
        let validator = StringLengthValidator {
            min: None,
            max: Some(5),
        };
        let result = validator.validate(&"hi".to_string(), "field");
        assert!(result.valid);
    }

    #[test]
    fn test_string_length_validator_max_invalid() {
        let validator = StringLengthValidator {
            min: None,
            max: Some(3),
        };
        let result = validator.validate(&"hello".to_string(), "field");
        assert!(!result.valid);
        assert_eq!(result.errors[0].code, "max_length");
    }

    #[test]
    fn test_string_length_validator_range() {
        let validator = StringLengthValidator {
            min: Some(2),
            max: Some(5),
        };
        assert!(validator.validate(&"hi".to_string(), "field").valid);
        assert!(validator.validate(&"hello".to_string(), "field").valid);
        assert!(!validator.validate(&"x".to_string(), "field").valid);
        assert!(!validator.validate(&"toolong".to_string(), "field").valid);
    }

    // -----------------------------------------------------------------------
    // NumericRangeValidator Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_numeric_range_validator_min_valid() {
        let validator = NumericRangeValidator {
            min: Some(0.0),
            max: None,
        };
        let result = validator.validate(&5.5, "field");
        assert!(result.valid);
    }

    #[test]
    fn test_numeric_range_validator_min_invalid() {
        let validator = NumericRangeValidator {
            min: Some(10.0),
            max: None,
        };
        let result = validator.validate(&5.5, "field");
        assert!(!result.valid);
        assert_eq!(result.errors[0].code, "min_value");
    }

    #[test]
    fn test_numeric_range_validator_max_valid() {
        let validator = NumericRangeValidator {
            min: None,
            max: Some(100.0),
        };
        let result = validator.validate(&50.0, "field");
        assert!(result.valid);
    }

    #[test]
    fn test_numeric_range_validator_max_invalid() {
        let validator = NumericRangeValidator {
            min: None,
            max: Some(50.0),
        };
        let result = validator.validate(&100.0, "field");
        assert!(!result.valid);
        assert_eq!(result.errors[0].code, "max_value");
    }

    // -----------------------------------------------------------------------
    // EnumValidator Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_enum_validator_valid() {
        let validator = EnumValidator {
            variants: &["red", "green", "blue"],
        };
        let result = validator.validate(&"red".to_string(), "field");
        assert!(result.valid);
    }

    #[test]
    fn test_enum_validator_invalid() {
        let validator = EnumValidator {
            variants: &["red", "green", "blue"],
        };
        let result = validator.validate(&"yellow".to_string(), "field");
        assert!(!result.valid);
        assert_eq!(result.errors[0].code, "invalid_value");
    }

    // -----------------------------------------------------------------------
    // EmailValidator Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_email_validator_valid() {
        let validator = EmailValidator;
        assert!(validator.validate(&"test@example.com".to_string(), "field").valid);
        assert!(validator.validate(&"user.name@company.co.uk".to_string(), "field").valid);
        assert!(validator.validate(&"a@b.co".to_string(), "field").valid);
    }

    #[test]
    fn test_email_validator_invalid() {
        let validator = EmailValidator;
        assert!(!validator.validate(&"notanemail".to_string(), "field").valid);
        assert!(!validator.validate(&"@example.com".to_string(), "field").valid);
        assert!(!validator.validate(&"user@".to_string(), "field").valid);
        assert!(!validator.validate(&"user@example".to_string(), "field").valid);
    }

    // -----------------------------------------------------------------------
    // validate_email Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_email_function() {
        assert!(validate_email("test@example.com"));
        assert!(validate_email("user+tag@domain.co.uk"));
        assert!(!validate_email("invalid.email"));
        assert!(!validate_email("@example.com"));
    }

    // -----------------------------------------------------------------------
    // validate_phone Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_phone() {
        assert!(validate_phone("+1-555-123-4567"));
        assert!(validate_phone("5551234567"));
        assert!(validate_phone("1-800-000-0000"));
        assert!(!validate_phone("123")); // too short
        assert!(!validate_phone("1234567890123456")); // too long
    }

    // -----------------------------------------------------------------------
    // validate_uuid Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_uuid() {
        assert!(validate_uuid("550e8400-e29b-41d4-a716-446655440000"));
        assert!(validate_uuid("123e4567-e89b-12d3-a456-426614174000"));
        assert!(!validate_uuid("not-a-uuid"));
        assert!(!validate_uuid("550e8400-e29b-41d4-a716"));
        assert!(!validate_uuid("550e8400-e29b-41d4-a716-44665544000z"));
    }

    // -----------------------------------------------------------------------
    // validate_hex_string Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_hex_string() {
        assert!(validate_hex_string("ff00ff00", 4));
        assert!(validate_hex_string("DEADBEEF", 4));
        assert!(!validate_hex_string("gg00gg00", 4)); // invalid hex
        assert!(!validate_hex_string("ff00ff", 4)); // wrong length
    }

    // -----------------------------------------------------------------------
    // validate_timestamp Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_timestamp() {
        // Valid timestamps
        assert!(validate_timestamp(946684800000)); // 2000-01-01
        assert!(validate_timestamp(1577836800000)); // 2020-01-01
        assert!(validate_timestamp(1687392000000)); // 2023-06-21

        // Invalid timestamps
        assert!(!validate_timestamp(100)); // too old
        assert!(!validate_timestamp(5000000000000)); // too far in future
    }

    // -----------------------------------------------------------------------
    // validate_symbol Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_symbol() {
        assert!(validate_symbol("BTC/USD"));
        assert!(validate_symbol("ETH/EUR"));
        assert!(validate_symbol("AAPL/USD"));
        assert!(!validate_symbol("BTC")); // missing pair
        assert!(!validate_symbol("BTC/USD/EUR")); // too many parts
        assert!(!validate_symbol("btc/usd")); // lowercase
    }

    // -----------------------------------------------------------------------
    // validate_instrument_id Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_instrument_id() {
        assert!(validate_instrument_id("ab"));
        assert!(validate_instrument_id("btcusd"));
        assert!(validate_instrument_id("spot0123456789"));
        assert!(!validate_instrument_id("a")); // too short
        assert!(!validate_instrument_id("A")); // uppercase
        assert!(!validate_instrument_id("abcdefghijklmnopqrstuv")); // too long
    }

    // -----------------------------------------------------------------------
    // validate_price Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_price() {
        assert!(validate_price(0.01));
        assert!(validate_price(100.50));
        assert!(validate_price(999.99));
        assert!(!validate_price(0.0)); // zero
        assert!(!validate_price(-10.0)); // negative
        assert!(!validate_price(1_000_000_000.0)); // too large
    }

    // -----------------------------------------------------------------------
    // validate_quantity Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_quantity() {
        assert!(validate_quantity(1.0));
        assert!(validate_quantity(1000.0));
        assert!(validate_quantity(50_000_000.0));
        assert!(!validate_quantity(0.0)); // zero
        assert!(!validate_quantity(-10.0)); // negative
        assert!(!validate_quantity(100_000_000.0)); // at max boundary
    }

    // -----------------------------------------------------------------------
    // validate_order_payload Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_order_payload_valid_market_buy() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "market",
            "quantity": 10.5
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(result.valid);
    }

    #[test]
    fn test_validate_order_payload_valid_limit_sell() {
        let payload = serde_json::json!({
            "side": "sell",
            "type": "limit",
            "quantity": 20.0,
            "price": 150.50,
            "time_in_force": "gtc"
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(result.valid);
    }

    #[test]
    fn test_validate_order_payload_missing_side() {
        let payload = serde_json::json!({
            "type": "market",
            "quantity": 10.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "side"));
    }

    #[test]
    fn test_validate_order_payload_invalid_side() {
        let payload = serde_json::json!({
            "side": "invalid",
            "type": "market",
            "quantity": 10.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "side"));
    }

    #[test]
    fn test_validate_order_payload_missing_type() {
        let payload = serde_json::json!({
            "side": "buy",
            "quantity": 10.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "type"));
    }

    #[test]
    fn test_validate_order_payload_invalid_type() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "invalid_type",
            "quantity": 10.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "type"));
    }

    #[test]
    fn test_validate_order_payload_missing_quantity() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "market"
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "quantity"));
    }

    #[test]
    fn test_validate_order_payload_zero_quantity() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "market",
            "quantity": 0.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "quantity"));
    }

    #[test]
    fn test_validate_order_payload_excessive_quantity() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "market",
            "quantity": 2_000_000.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "quantity"));
    }

    #[test]
    fn test_validate_order_payload_limit_order_missing_price() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "limit",
            "quantity": 10.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "price"));
    }

    #[test]
    fn test_validate_order_payload_limit_order_invalid_price() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "limit",
            "quantity": 10.0,
            "price": 0.0
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "price"));
    }

    #[test]
    fn test_validate_order_payload_invalid_tif() {
        let payload = serde_json::json!({
            "side": "buy",
            "type": "limit",
            "quantity": 10.0,
            "price": 100.0,
            "time_in_force": "invalid_tif"
        });
        let result = MessageValidator::validate_order_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "time_in_force"));
    }

    // -----------------------------------------------------------------------
    // validate_account_payload Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_validate_account_payload_valid() {
        let payload = serde_json::json!({
            "amount": 1000.0,
            "currency": "USD"
        });
        let result = MessageValidator::validate_account_payload(&payload);
        assert!(result.valid);
    }

    #[test]
    fn test_validate_account_payload_zero_amount() {
        let payload = serde_json::json!({
            "amount": 0.0,
            "currency": "USD"
        });
        let result = MessageValidator::validate_account_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "amount"));
    }

    #[test]
    fn test_validate_account_payload_negative_amount() {
        let payload = serde_json::json!({
            "amount": -100.0,
            "currency": "USD"
        });
        let result = MessageValidator::validate_account_payload(&payload);
        assert!(!result.valid);
    }

    #[test]
    fn test_validate_account_payload_excessive_amount() {
        let payload = serde_json::json!({
            "amount": 2_000_000_000.0,
            "currency": "USD"
        });
        let result = MessageValidator::validate_account_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "amount"));
    }

    #[test]
    fn test_validate_account_payload_invalid_currency() {
        let payload = serde_json::json!({
            "amount": 100.0,
            "currency": "INVALID"
        });
        let result = MessageValidator::validate_account_payload(&payload);
        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.field == "currency"));
    }

    #[test]
    fn test_validate_account_payload_valid_currencies() {
        for currency in &["USD", "EUR", "GBP", "BTC", "ETH", "USDT", "USDC"] {
            let payload = serde_json::json!({
                "amount": 100.0,
                "currency": currency
            });
            let result = MessageValidator::validate_account_payload(&payload);
            assert!(result.valid, "Currency {} should be valid", currency);
        }
    }

    // -----------------------------------------------------------------------
    // Severity enum Tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_severity_equality() {
        assert_eq!(Severity::Error, Severity::Error);
        assert_eq!(Severity::Warning, Severity::Warning);
        assert_eq!(Severity::Info, Severity::Info);
        assert_ne!(Severity::Error, Severity::Warning);
    }
}
