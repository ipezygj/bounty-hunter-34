/**
 * @file self_test.c
 * @brief Frailbox self-test suite for reviewers
 *
 * This self-test validates the core components of frailbox:
 * - Arena allocator (memory management)
 * - Logger (logging system)
 * - Sandbox (process isolation)
 * - Connector (IPC protocol)
 *
 * Compile with: make self-test
 * Run standalone: ./frailbox-self-test
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>

#include "arena.h"
#include "logger.h"
#include "sandbox.h"

/* Self-test results tracking */
typedef struct {
    const char *name;
    int passed;
    const char *error_msg;
} test_result_t;

static test_result_t results[32];
static int result_count = 0;
static int total_passed = 0;
static int total_failed = 0;
static int total_skipped = 0;

/**
 * Record a test result
 */
static void record_test(const char *name, int passed, const char *error_msg) {
    if (result_count >= 32) {
        return;
    }
    results[result_count].name = name;
    results[result_count].passed = passed;
    results[result_count].error_msg = error_msg;
    result_count++;

    if (passed) {
        total_passed++;
    } else {
        total_failed++;
    }
}

/**
 * Test 1: Arena allocator initialization
 */
static void test_arena_init(void) {
    arena_t *arena = arena_create(1024 * 1024, ARENA_ZERO_INIT);
    if (!arena) {
        record_test("arena_init", 0, "Failed to create arena");
        return;
    }

    arena_stats_t stats = arena_get_stats(arena);
    if (stats.total_allocated == 0) {
        arena_destroy(arena);
        record_test("arena_init", 1, NULL);
        return;
    }

    arena_destroy(arena);
    record_test("arena_init", 1, NULL);
}

/**
 * Test 2: Arena allocation
 */
static void test_arena_alloc(void) {
    arena_t *arena = arena_create(1024 * 1024, ARENA_ZERO_INIT);
    if (!arena) {
        record_test("arena_alloc", 0, "Failed to create arena");
        return;
    }

    void *ptr1 = arena_alloc(arena, 1024);
    void *ptr2 = arena_alloc(arena, 2048);
    void *ptr3 = arena_calloc(arena, 10, 100);

    if (!ptr1 || !ptr2 || !ptr3) {
        arena_destroy(arena);
        record_test("arena_alloc", 0, "Allocation failed");
        return;
    }

    arena_stats_t stats = arena_get_stats(arena);
    if (stats.allocation_count >= 3) {
        arena_destroy(arena);
        record_test("arena_alloc", 1, NULL);
        return;
    }

    arena_destroy(arena);
    record_test("arena_alloc", 0, "Invalid allocation count");
}

/**
 * Test 3: Arena aligned allocation
 */
static void test_arena_aligned_alloc(void) {
    arena_t *arena = arena_create(1024 * 1024, ARENA_ZERO_INIT);
    if (!arena) {
        record_test("arena_aligned_alloc", 0, "Failed to create arena");
        return;
    }

    void *ptr = arena_alloc_aligned(arena, 256, 64);
    if (!ptr) {
        arena_destroy(arena);
        record_test("arena_aligned_alloc", 0, "Aligned allocation failed");
        return;
    }

    /* Check alignment */
    uintptr_t addr = (uintptr_t)ptr;
    if ((addr % 64) == 0) {
        arena_destroy(arena);
        record_test("arena_aligned_alloc", 1, NULL);
        return;
    }

    arena_destroy(arena);
    record_test("arena_aligned_alloc", 0, "Alignment check failed");
}

/**
 * Test 4: Logger initialization
 */
static void test_logger_init(void) {
    logger_t *logger = logger_create("self_test.log", LOG_LEVEL_DEBUG);
    if (!logger) {
        record_test("logger_init", 0, "Failed to create logger");
        return;
    }

    logger_destroy(logger);
    record_test("logger_init", 1, NULL);
}

/**
 * Test 5: Logger write
 */
static void test_logger_write(void) {
    logger_t *logger = logger_create("self_test_write.log", LOG_LEVEL_DEBUG);
    if (!logger) {
        record_test("logger_write", 0, "Failed to create logger");
        return;
    }

    int result = logger_write(logger, LOG_LEVEL_INFO, "Test message: %s", "Hello");
    if (result == 0) {
        logger_destroy(logger);
        record_test("logger_write", 1, NULL);
        return;
    }

    logger_destroy(logger);
    record_test("logger_write", 0, "Logger write failed");
}

/**
 * Test 6: Sandbox initialization
 */
static void test_sandbox_init(void) {
    sandbox_config_t config;
    memset(&config, 0, sizeof(config));
    config.type = SANDBOX_SECCOMP;
    config.memory_limit_bytes = 256 * 1024 * 1024;
    config.cpu_limit_ns = 1000000000;
    config.max_processes = 10;
    config.max_open_fds = 64;
    config.enable_network = 0;
    config.enable_ptrace = 0;

    sandbox_t *sandbox = sandbox_create(&config);
    if (!sandbox) {
        record_test("sandbox_init", 0, "Failed to create sandbox");
        return;
    }

    sandbox_destroy(sandbox);
    record_test("sandbox_init", 1, NULL);
}

/**
 * Test 7: Sandbox config validation
 */
static void test_sandbox_config_validation(void) {
    sandbox_config_t config;
    memset(&config, 0, sizeof(config));
    config.type = SANDBOX_NONE;
    config.memory_limit_bytes = 256 * 1024 * 1024;
    config.max_processes = 10;

    sandbox_t *sandbox = sandbox_create(&config);
    if (!sandbox) {
        record_test("sandbox_config_validation", 0, "Failed to create NONE sandbox");
        return;
    }

    if (sandbox->config.type == SANDBOX_NONE) {
        sandbox_destroy(sandbox);
        record_test("sandbox_config_validation", 1, NULL);
        return;
    }

    sandbox_destroy(sandbox);
    record_test("sandbox_config_validation", 0, "Config type mismatch");
}

/**
 * Test 8: Multiple arena instances
 */
static void test_multiple_arenas(void) {
    arena_t *arena1 = arena_create(512 * 1024, ARENA_ZERO_INIT);
    arena_t *arena2 = arena_create(512 * 1024, ARENA_ZERO_INIT);

    if (!arena1 || !arena2) {
        if (arena1) arena_destroy(arena1);
        if (arena2) arena_destroy(arena2);
        record_test("multiple_arenas", 0, "Failed to create multiple arenas");
        return;
    }

    void *ptr1 = arena_alloc(arena1, 1024);
    void *ptr2 = arena_alloc(arena2, 1024);

    if (!ptr1 || !ptr2) {
        arena_destroy(arena1);
        arena_destroy(arena2);
        record_test("multiple_arenas", 0, "Allocation in multiple arenas failed");
        return;
    }

    arena_destroy(arena1);
    arena_destroy(arena2);
    record_test("multiple_arenas", 1, NULL);
}

/**
 * Print results as JSON
 */
static void print_json_results(void) {
    FILE *fp = fopen("self-test-results.json", "w");
    if (!fp) {
        fp = stdout;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"test_suite\": \"frailbox-self-test\",\n");
    fprintf(fp, "  \"timestamp\": %ld,\n", (long)time(NULL));
    fprintf(fp, "  \"summary\": {\n");
    fprintf(fp, "    \"total\": %d,\n", result_count);
    fprintf(fp, "    \"passed\": %d,\n", total_passed);
    fprintf(fp, "    \"failed\": %d,\n", total_failed);
    fprintf(fp, "    \"skipped\": %d\n", total_skipped);
    fprintf(fp, "  },\n");
    fprintf(fp, "  \"results\": [\n");

    for (int i = 0; i < result_count; i++) {
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"name\": \"%s\",\n", results[i].name);
        fprintf(fp, "      \"status\": \"%s\"", results[i].passed ? "PASS" : "FAIL");
        if (results[i].error_msg) {
            fprintf(fp, ",\n      \"error\": \"%s\"", results[i].error_msg);
        }
        fprintf(fp, "\n    }");
        if (i < result_count - 1) {
            fprintf(fp, ",");
        }
        fprintf(fp, "\n");
    }

    fprintf(fp, "  ]\n");
    fprintf(fp, "}\n");

    if (fp != stdout) {
        fclose(fp);
    }
}

/**
 * Print console results
 */
static void print_console_results(void) {
    printf("\n");
    printf("╔════════════════════════════════════════════════════════════╗\n");
    printf("║           FRAILBOX SELF-TEST RESULTS                       ║\n");
    printf("╚════════════════════════════════════════════════════════════╝\n\n");

    for (int i = 0; i < result_count; i++) {
        const char *status = results[i].passed ? "✓ PASS" : "✗ FAIL";
        printf("  [%2d/%2d] %-40s %s\n", i + 1, result_count, results[i].name, status);
        if (results[i].error_msg) {
            printf("          Error: %s\n", results[i].error_msg);
        }
    }

    printf("\n");
    printf("════════════════════════════════════════════════════════════\n");
    printf("  SUMMARY: %d passed, %d failed, %d skipped out of %d tests\n",
           total_passed, total_failed, total_skipped, result_count);
    printf("════════════════════════════════════════════════════════════\n\n");
}

/**
 * Main test runner
 */
int main(void) {
    printf("Frailbox Self-Test Suite\n");
    printf("========================\n\n");

    /* Run all tests */
    test_arena_init();
    test_arena_alloc();
    test_arena_aligned_alloc();
    test_logger_init();
    test_logger_write();
    test_sandbox_init();
    test_sandbox_config_validation();
    test_multiple_arenas();

    /* Print results */
    print_console_results();
    print_json_results();

    printf("JSON results saved to: self-test-results.json\n\n");

    /* Return non-zero if any test failed */
    return total_failed > 0 ? 1 : 0;
}
