# Agent 1 — Security Re-audit Report

**Date:** 2026-03-30  
**Scope:** Automated-agent changes in commit `db12b2f` (feat: orchestrated agent improvements)

---

## Summary

**All clear. No security issues found.**  
The automated agents' changes are correct, safe, and do not introduce any new attack surface or information leakage.

---

## 1. Python Files — Guard Correctness Review

### `api.py`

| Guard | Assessment |
|---|---|
| `isinstance(data, dict)` before `.get("departures", [])` | ✅ Correct. Prevents `AttributeError` if API returns a list/null. |
| `isinstance(data, dict)` before `.get("locations", [])` in `find_stops()` | ✅ Correct. Same reasoning. |
| `_read_json()` with `MAX_RESPONSE_BYTES` (512 KB) cap | ✅ Correct and sufficient. Prevents memory exhaustion from oversized/malicious payloads. |
| `_parse_site_id()` returns 0 on non-numeric or empty input | ✅ Safe default. Caller filters out `site_id == 0`. |
| Broad `except Exception` in `_parse_departure` / `_parse_stop` (BLE001 noqa) | ✅ Acceptable — parse failures log a warning and return None, which is discarded. Does not swallow critical errors upstream. |

### `coordinator.py`

| Guard | Assessment |
|---|---|
| `valid_routes = [r for r in self.routes if "\|" in r]` | ✅ Correct route format validation. Silently drops malformed route strings (no `\|` separator). |
| `all_zero_dc` fallback to line-only matching | ✅ Correct backwards-compatibility behaviour for legacy entries. |
| Explicit `SLApiRateLimitError` → `UpdateFailed` (with warning, not error) | ✅ Good UX — won't spam the HA log on transient rate limits. |

### `sensor.py`

| Guard | Assessment |
|---|---|
| `isinstance(self.coordinator.data, list)` guards in `SLDeparturesSensor` | ✅ Correct. Prevents crash if coordinator data is None or wrong type during startup. |
| `isinstance(self.coordinator.data, list)` guard in `SLStatusSensor` | ✅ Correct. |

### `config_flow.py`

- Route values come from live API departures; the selector is pre-populated with values the API itself returned — no user-controlled free-text route injection.
- `vol.Length(min=2, max=100)` on the stop search query prevents trivially empty or very long queries.
- `vol.In(stop_options)` on site_id selection ensures only valid discovered IDs can be chosen — no SSRF path via an arbitrary site_id.

**No issues found in any Python file.**

---

## 2. Test Files — Secrets / PII Scan

Searched all test files for: passwords, tokens, API keys, private IP ranges (192.168.x.x, 10.x.x.x, 172.16-31.x.x), localhost, email addresses, personal names.

**Results:**
- ✅ No hardcoded secrets, tokens, or API keys.
- ✅ No private IP addresses or internal hostnames.
- ✅ No personal data (real names, emails, etc.).
- ✅ Test stop names used: `"Test Stop"`, `"Test City, Bus Terminal"`, `"Test City, Metro Station"` — clearly synthetic.
- ✅ Test stop IDs: `7067`, `9117`, `9529` — valid-format SL site IDs, publicly known from SL's open API, not user-private data.
- ✅ Test line numbers: `172`, `726`, `744` — real Stockholm bus lines, publicly known, not sensitive.
- ✅ Dates used in tests: `2026-03-21` — future test fixture date, no personal significance.

---

## 3. CHANGELOG.md — Internal Detail Review

The CHANGELOG contains only:
- Feature descriptions using public API terminology (Trafiklab, SL Transport API)
- Configuration option names that are already in the HA UI
- No internal hostnames, IP addresses, usernames, credentials, or infrastructure details
- No references to private repositories, internal tools, or deployment details

**No leakage found.**

---

## 4. Test Suite Results

```
71 tests collected, 71 passed, 0 failed, 0 errors (0.61s)
```

Full breakdown:
- `tests/test_api.py` — 33 tests: PASSED
- `tests/test_coordinator.py` — 17 tests: PASSED  
- `tests/test_sensor.py` — 21 tests: PASSED

---

## 5. Minor Observations (Non-Security)

These are not security issues, but worth noting for completeness:

1. **`conftest.py` mocks `voluptuous` only if not already installed** — voluptuous is actually installed in the environment, so the mock branch is dead code. Harmless.

2. **Route injection from API** — `_fetch_route_options()` builds route values from live API responses. If the SL API were compromised, it could inject arbitrary `value` strings into the selector. However: (a) these values are only used for client-side filtering of the same API's data; (b) they go through `|` format validation before use; (c) they are never executed or passed to a shell. Risk: negligible.

3. **`except Exception` with noqa BLE001** in parse functions — these are intentional lenient parsers. Acceptable for a HA integration where a single bad departure row should not crash the whole update. Noted for awareness.

---

## Verdict

✅ **Clean.** The automated agent improvements are correct and safe. No secrets, no PII, no injection vectors, no dangerous guards, no CHANGELOG leakage. Test suite passes 100%.
