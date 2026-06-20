# Pre-commit Hook Documentation

## Overview

The pre-commit hook automatically runs `build.py` before each commit to generate diagnostic artifacts. This ensures that diagnostic files are always up-to-date and included in commits, preventing the diagnostic-build-log GitHub Action from rejecting PRs.

## Features

- **Automatic Build Execution**: Runs `python3 build.py` before every commit
- **Diagnostic Artifact Staging**: Automatically stages generated `.logd` and `.json` files
- **Build Failure Protection**: Aborts commit if `build.py` fails with a clear error message
- **Smart Caching**: Skips rebuild if source files haven't changed since last commit (using SHA-256 hash comparison)
- **Progress Feedback**: Shows a countdown timer during the build process
- **Multi-part Support**: Handles both single and multi-part `.logd` files

## Installation

### Quick Install

From the repository root, run:

```bash
make install-hooks
```

This will:
1. Create `.git/hooks/` directory if it doesn't exist
2. Create a symlink from `.git/hooks/pre-commit` to `tools/pre-commit`
3. Make the script executable
4. Back up any existing pre-commit hook to `.git/hooks/pre-commit.backup`

### Manual Installation

If you prefer to install manually:

```bash
# Make the script executable
chmod +x tools/pre-commit

# Create symlink
ln -s ../../tools/pre-commit .git/hooks/pre-commit
```

### Verification

To verify the hook is installed correctly:

```bash
ls -la .git/hooks/pre-commit
```

You should see a symlink pointing to `../../tools/pre-commit`.

## Usage

### Normal Workflow

Once installed, the hook runs automatically on every commit:

```bash
git add your-changes.py
git commit -m "Your commit message"
```

The hook will:
1. Check if source files have changed since the last build
2. Run `build.py` if needed (with countdown timer)
3. Find and stage the latest diagnostic artifacts
4. Allow the commit to proceed if successful

### Skipping the Hook

To temporarily skip the hook (not recommended):

```bash
git commit --no-verify -m "Your commit message"
```

**Warning**: Skipping the hook will likely cause your PR to fail the diagnostic-build-log GitHub Action.

### Uninstalling

To remove the hook:

```bash
make uninstall-hooks
```

Or manually:

```bash
rm .git/hooks/pre-commit
```

## How It Works

### 1. Source Hash Computation

The hook computes a SHA-256 hash of all `.py` files in the repository to detect changes since the last build.

### 2. Cache Check

If the source hash matches the cached hash from the previous run, and diagnostic files exist, the hook skips the rebuild and uses cached diagnostics.

### 3. Build Execution

If a rebuild is needed:
- Runs `python3 build.py` with a 10-minute timeout
- Shows a countdown timer with estimated completion time (5 minutes)
- Captures stdout and stderr for error reporting

### 4. Artifact Discovery

The hook looks for diagnostic files matching the pattern:
- `diagnostic/build-*.logd` (single files)
- `diagnostic/build-*-part*.logd` (multi-part files)
- `diagnostic/build-*.json` (metadata files)

It finds the most recent build ID and stages all files associated with it.

### 5. Git Staging

All discovered diagnostic files are added to the git staging area using `git add`.

### 6. Cache Update

On success, the hook saves:
- Current source hash
- List of staged diagnostic files

This cache is stored in `.git/pre-commit-cache.json`.

## Error Handling

### Build Failure

If `build.py` fails, the hook:
1. Displays the error message and exit code
2. Shows stderr and stdout output
3. Aborts the commit with: `COMMIT ABORTED: Fix build errors and try again`

### Missing Diagnostic Files

If the build succeeds but no diagnostic files are generated:
1. Displays a warning about potential encryptly issues
2. Aborts the commit with: `COMMIT ABORTED: No diagnostic artifacts found`

### Staging Failure

If diagnostic files cannot be staged:
1. Shows which file failed and why
2. Aborts the commit with: `COMMIT ABORTED: Could not stage diagnostic artifacts`

## Troubleshooting

### Hook Not Running

Check if the hook is installed:
```bash
ls -la .git/hooks/pre-commit
```

Make sure it's executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Build Timeout

If builds consistently timeout (> 10 minutes), you may need to:
- Increase the timeout in `tools/pre-commit` (line 168)
- Check for issues with the `encryptly` tool
- Verify all build dependencies are installed

### Encryptly Issues

The `encryptly` tool may hang or timeout. The hook will report this as a build failure. To debug:

1. Run `build.py` manually:
   ```bash
   python3 build.py
   ```

2. Check for platform-specific encryptly binary:
   ```bash
   ls -la tools/encryptly/
   ```

3. Verify your platform is supported (linux-x64, linux-arm64, macos-x64, macos-arm64, windows-x64, windows-arm64)

### Cache Issues

If caching behaves incorrectly, delete the cache:
```bash
rm .git/pre-commit-cache.json
```

The next commit will rebuild from scratch.

## Performance

### First Commit
- Full build: ~5-10 minutes (depends on modules)
- Includes all module builds (Rust, TypeScript, Go, C, C++, Java, Ruby, Lua, Haskell)

### Subsequent Commits (No Changes)
- Cache hit: <1 second
- Only stages existing diagnostic files

### Subsequent Commits (With Changes)
- Full rebuild: ~5-10 minutes
- New diagnostic artifacts generated and staged

## Technical Details

### File Structure
```
tools/
  pre-commit           # Main hook script (Python)
Makefile               # Install/uninstall targets
docs/
  pre-commit-hook.md   # This documentation
.git/
  hooks/
    pre-commit         # Symlink to tools/pre-commit
  pre-commit-cache.json  # Cache file (git-ignored)
diagnostic/
  build-*.logd         # Generated diagnostic logs
  build-*.json         # Generated diagnostic metadata
```

### Dependencies
- Python 3.6+
- Git
- All dependencies required by `build.py` (Rust, Node.js, Go, etc.)

### Exit Codes
- `0`: Success (commit proceeds)
- `1`: Failure (commit aborted)

## Contributing

When modifying the pre-commit hook:

1. Test thoroughly with various scenarios:
   - Fresh repository
   - Cached builds
   - Failed builds
   - Missing dependencies

2. Update this documentation if behavior changes

3. Ensure the hook remains fast for cache hits (< 1 second)

4. Keep error messages clear and actionable

## See Also

- [build.py](../build.py) - Main build script
- [.github/workflows/diagnostic-build-log.yml](../.github/workflows/diagnostic-build-log.yml) - CI workflow
- [GitHub Actions: Pre-commit Hooks](https://github.com/pre-commit/pre-commit)
