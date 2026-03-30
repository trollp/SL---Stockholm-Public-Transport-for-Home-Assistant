# Release Notes — v1.1.0

This release focuses on code quality, test coverage, and documentation polish. No breaking changes.

## What's New

### 🧪 Expanded Test Coverage (38 → 71 tests)
The test suite has nearly doubled in size. New tests cover sensor state edge cases, config flow error handling, and coordinator update logic — making the integration significantly more robust and easier to maintain.

### 🛡️ Code Quality Guards
Pre-commit hooks and linting rules are now enforced in CI, ensuring consistent code style and catching regressions before they land. Dead code removed, type annotations improved throughout.

### 📚 Documentation Improvements
- README reorganized with clearer troubleshooting steps, example automations, and API reference
- CHANGELOG kept up to date going forward

## Upgrade Notes

- Drop-in replacement for v1.0.0 — no configuration changes required
- Restart Home Assistant after updating via HACS or manually copying files
