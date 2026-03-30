# Agent 2 — Integration Validator Report

**Date:** 2026-03-30  
**Integration:** SL — Stockholm Public Transport (`custom_components/sl`)  
**Target quality level:** Bronze (as declared in `manifest.json`)

---

## Summary

The integration is in **good shape overall**. All 71 unit tests pass. The core architecture is correct and modern. There are a few minor issues to fix before HACS submission, none of which are blockers on their own, but together they could cause `hassfest` failures or user-facing bugs.

---

## 1. Bronze Quality Scale Checklist

Bronze criteria per HA developer docs:

| Requirement | Status | Notes |
|---|---|---|
| `config_flow: true` in manifest | ✅ | Set correctly |
| Unique entity IDs | ✅ | `f"{entry.entry_id}_{sensor_type}"` — correct and stable |
| Error handling in coordinator | ✅ | `SLApiConnectionError`, `SLApiRateLimitError`, `SLApiError` all caught and converted to `UpdateFailed` |
| Has tests | ✅ | 71 tests across api, coordinator, and sensor — all pass |
| Uses `DataUpdateCoordinator` | ✅ | Correct pattern |
| Uses `CoordinatorEntity` | ✅ | `SLBaseSensor` inherits from `CoordinatorEntity` |
| `async_setup_entry` / `async_unload_entry` | ✅ | Both present and correct |
| Options flow | ✅ | `SLOptionsFlow` properly implemented |
| `entry.runtime_data` pattern | ✅ | Used instead of legacy `hass.data` |
| `_attr_has_entity_name = True` | ✅ | Set on `SLBaseSensor` |
| `DeviceInfo` on entities | ✅ | All sensors have device info |

**Bronze verdict: PASS** — all requirements are met.

---

## 2. Bugs / Issues Found

### 🐛 BUG (Medium): `sensor.py` reads `departures_count` from `entry.data` only — ignores options

**File:** `sensor.py`, line 39  
**Problem:** `departures_count = entry.data.get(CONF_DEPARTURES_COUNT, 3)` reads only from `entry.data`. The options flow allows the user to change `departures_count`, and `__init__.py` correctly merges `entry.data` + `entry.options` for `forecast` and `routes`. But `sensor.py` skips this merge — so changing `departures_count` via the options flow has no effect until the entry is fully deleted and re-added.

**Fix:**
```python
# sensor.py, inside async_setup_entry
config = {**entry.data, **entry.options}  # mirror what __init__.py does
departures_count = config.get(CONF_DEPARTURES_COUNT, 3)
```

Note: since `async_update_options` reloads the entry, the entities are recreated on options change — so this fix will work correctly once applied.

### ⚠️ ISSUE (Low): No `quality_scale.yaml` file

**Problem:** `manifest.json` declares `"quality_scale": "bronze"`, but there is no `quality_scale.yaml` file in `custom_components/sl/`. Recent versions of `hassfest` (the HA CI validator) require this file to exist when `quality_scale` is declared in the manifest.

**Fix:** Create `custom_components/sl/quality_scale.yaml` documenting the rules met/exempt:
```yaml
rules:
  config-flow: done
  test-coverage: done
  unique-config-entry-per-device-or-service: done
  # ... add other applicable bronze rules
```

Alternatively, remove `"quality_scale": "bronze"` from the manifest until the file is added. HACS itself doesn't require it, but `hassfest` will flag the absence.

### ⚠️ ISSUE (Low): `SLDeparturesSensor` uses `"departures"` as unit of measurement

**File:** `sensor.py`, line ~102  
```python
self._attr_native_unit_of_measurement = "departures"
```
This is a non-standard unit. HA won't reject it, but it will appear in the UI and in statistics. Consider setting it to `None` or removing it entirely — the sensor value (an integer count) is self-explanatory through its name. Not a blocker, but slightly odd UX.

---

## 3. Anti-Patterns Check

| Pattern | Result |
|---|---|
| Blocking I/O (`requests`, `urllib`, `time.sleep`, `open()`) in async context | ✅ None found — all HTTP is via `aiohttp` |
| Missing `async_` prefix on HA callbacks | ✅ Clean |
| Using `hass.data` instead of `entry.runtime_data` | ✅ Uses `runtime_data` correctly |
| Importing `homeassistant` modules at function call level (slow) | ✅ All imports at module level |
| Coordinator calling HA APIs directly | ✅ Coordinator only calls `self.client` |
| Incorrect entity base class | ✅ `CoordinatorEntity[SLDepartureCoordinator]` + `SensorEntity` — correct |
| `update_before_add=True` in `async_add_entities` | ⚠️ Used in `sensor.py` line ~42. This triggers an immediate fetch on setup *in addition* to `coordinator.async_config_entry_first_refresh()` in `__init__.py`. Double-fetching on setup. Not harmful but wasteful — consider removing it since the coordinator is already refreshed before setup. |

---

## 4. Translations Audit

### strings.json vs en.json
Both files are **identical** — every key in `strings.json` exists in `en.json` and vice versa. ✅

### strings.json vs sv.json
All structural keys match. All config flow steps, errors, abort messages, and entity translations are present in Swedish. ✅

**One minor note:** The `options.step.options` section in all three files lacks a `description` key (the `config.step.options` section does have one). This is not an error — descriptions are optional — but it's an inconsistency that makes the options form slightly less user-friendly.

---

## 5. CI Workflow (`.github/workflows/validate.yml`)

### What's there:
- `hassfest` job — uses `home-assistant/actions/hassfest@master` ✅
- `hacs` job — uses `hacs/action@main` ✅
- `tests` job — installs `pytest aiohttp`, runs `pytest tests/ -v` ✅

### Issues:

**⚠️ `hassfest` and `hacs` actions pin to `master`/`main` (floating)**  
Using `@master` and `@main` is fine for official HA/HACS actions (they maintain these as stable pointers), but it's worth knowing they aren't pinned SHAs. Acceptable for a custom integration.

**⚠️ Tests job only installs `pytest` and `aiohttp`**  
The test suite works locally because the `conftest.py` stubs out all `homeassistant.*` imports. However, if a future test ever imports a real HA module (e.g., to test config_flow properly), it will fail in CI because `homeassistant` isn't installed. Consider adding `homeassistant` to the install step for robustness:
```yaml
pip install pytest aiohttp homeassistant
```
This isn't blocking since the current tests all pass with the stub approach.

**⚠️ No Python version matrix beyond 3.12**  
Only `python-version: ["3.12"]` is tested. HA 2024.1+ supports Python 3.12 only, so this is fine. But it's presented as a `strategy.matrix` for a single entry — minor cleanup opportunity.

**✅ Trigger conditions are correct** — runs on push and PR to `main`/`master`.

---

## 6. Overall Recommendation

The integration is **ready for HACS submission** after addressing:

1. **Must fix:** The `departures_count` options-flow bug in `sensor.py` (user setting ignored)
2. **Should fix:** Add `quality_scale.yaml` to prevent `hassfest` validation failure
3. **Nice to have:** Remove `update_before_add=True` to avoid double-fetch on setup
4. **Nice to have:** Add `description` to `options.step.options` in all translation files
