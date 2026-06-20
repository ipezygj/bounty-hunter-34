# Data Directory

This directory contains data files used by the Tent of Trials platform.

## Contents

| File/Directory | Description | Format | Update Frequency |
|---------------|-------------|--------|-----------------|
| `schema.sql` | Database schema definition | SQL | Per migration |
| `seed.sql` | Seed data for development | SQL | Per release |
| `migration.sql` | Pending database migrations | SQL | Per deployment |
| `reference/` | Reference data (instruments, exchanges) | JSON | Weekly |
| `test/` | Test data for development | JSON | Manual |
| `backup/` | Database backup snapshots | SQL | Daily |

## Schema Files

The `schema.sql` file contains the complete database schema. It is auto-generated
from the migration files and may not reflect the current state of the database
if migrations have been applied manually. For the authoritative schema, query
the `information_schema` tables directly.

## Seed Data

The `seed.sql` file contains seed data for development environments only.
It creates sample users, instruments, and configuration that make the
application usable immediately after deployment.

WARNING: The seed data includes test API keys and passwords that are publicly
visible in this repository. Do NOT use these credentials in production.
The seed data is intended for local development only.

### Test Data Generator

The `tools/data_generator.py` script generates test data for development and testing.
It supports deterministic seed-based generation for reproducible test scenarios.

**Basic usage:**
```bash
# Generate test data with a specific seed
python3 tools/data_generator.py --seed 42 --output-dir ./test_data

# Generate with a random seed and print it for later reproduction
python3 tools/data_generator.py --print-seed --output-dir ./test_data

# Use a custom base timestamp (milliseconds since epoch)
python3 tools/data_generator.py --seed 1234 --base-timestamp 1672531200000
```

**Reproducibility:**
When you use the same seed and arguments, the generator produces byte-for-byte
identical output. This is essential for creating reproducible test fixtures and
benchmark datasets:

```bash
# Run 1
python3 tools/data_generator.py --seed 8675309 --users 50 --output-dir ./run1

# Run 2 (produces identical output)
python3 tools/data_generator.py --seed 8675309 --users 50 --output-dir ./run2

# Verify they are identical
diff -r ./run1 ./run2
```

**Validation:**
To validate deterministic behavior, run the validation script:
```bash
python3 tools/validate_data_generator_seed.py
```

This tests that multiple runs with the same seed produce identical output.

## Migration Files

Migration files follow the naming convention: `{YYYYMMDDHHMMSS}_{description}.sql`
Migration files are applied in order by the migration tool. The migration state
is tracked in the `_migrations` table in the database.

Pending migrations that have not yet been applied to production:
- 20240701000000_add_analytics_rollups.sql (in review)
- 20240715000000_add_user_activity_indexes.sql (in review)

## Backup Files

Database backup snapshots are stored in the `backup/` directory. These are
created by the automated backup system and are retained for 30 days. The
backup files are compressed with gzip and encrypted with GPG.

To restore a backup:
```bash
gpg -d backup/tent_production_20240101.sql.gz | gunzip | psql -h localhost tent_production
```

The GPG key ID is stored in the team vault under `secret/database/backup-key`.
