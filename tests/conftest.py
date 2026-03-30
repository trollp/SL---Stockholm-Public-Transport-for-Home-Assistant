"""
Global test setup: register minimal HA stubs in sys.modules before any
custom_components imports happen.

When pytest imports tests/test_api.py, Python also executes
custom_components/sl/__init__.py (it's the package init), which in turn
imports homeassistant.* and voluptuous.  We intercept all of those here,
before collection starts, by using types.ModuleType stubs rather than
MagicMock (MagicMock-as-module causes issues with `from x import y`).
"""
from __future__ import annotations
import sys
import types
from unittest.mock import MagicMock


def _mod(name: str, **attrs) -> types.ModuleType:
    """Create a stub module and register it in sys.modules."""
    m = types.ModuleType(name)
    m.__package__ = name
    m.__path__ = []          # makes it look like a package to the importer
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# ------------------------------------------------------------------
# Purge any cached versions of our own package first
# ------------------------------------------------------------------
for _key in list(sys.modules):
    if _key.startswith("custom_components.sl"):
        del sys.modules[_key]


# ------------------------------------------------------------------
# homeassistant root
# ------------------------------------------------------------------
_ha = _mod("homeassistant")


# ------------------------------------------------------------------
# homeassistant.const
# ------------------------------------------------------------------
class _Platform:
    SENSOR = "sensor"

_mod("homeassistant.const", Platform=_Platform)


# ------------------------------------------------------------------
# homeassistant.core
# ------------------------------------------------------------------
def _callback(fn):
    return fn

_mod("homeassistant.core", HomeAssistant=object, callback=_callback)


# ------------------------------------------------------------------
# homeassistant.exceptions
# ------------------------------------------------------------------
class _HAError(Exception):
    pass

_mod("homeassistant.exceptions", HomeAssistantError=_HAError)


# ------------------------------------------------------------------
# homeassistant.config_entries
# ------------------------------------------------------------------
class _ConfigEntry:
    def __init__(self):
        self.data = {}
        self.options = {}
        self.entry_id = "test_entry"
        self.runtime_data = None

    def add_update_listener(self, _fn):
        return lambda: None

    def async_on_unload(self, _fn):
        pass

class _ConfigFlow:
    pass

class _OptionsFlow:
    pass

_mod(
    "homeassistant.config_entries",
    ConfigEntry=_ConfigEntry,
    ConfigFlow=_ConfigFlow,
    OptionsFlow=_OptionsFlow,
)


# ------------------------------------------------------------------
# homeassistant.data_entry_flow
# ------------------------------------------------------------------
_mod("homeassistant.data_entry_flow", FlowResult=dict)


# ------------------------------------------------------------------
# homeassistant.helpers
# ------------------------------------------------------------------
_mod("homeassistant.helpers")


# ------------------------------------------------------------------
# homeassistant.helpers.update_coordinator
# ------------------------------------------------------------------
class _DataUpdateCoordinator:
    """Minimal stand-in — supports DataUpdateCoordinator[T] syntax."""

    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None


class _UpdateFailed(Exception):
    pass


class _CoordinatorEntity:
    """Minimal stand-in — supports CoordinatorEntity[T] syntax."""

    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

_mod(
    "homeassistant.helpers.update_coordinator",
    DataUpdateCoordinator=_DataUpdateCoordinator,
    UpdateFailed=_UpdateFailed,
    CoordinatorEntity=_CoordinatorEntity,
)


# ------------------------------------------------------------------
# homeassistant.helpers.aiohttp_client
# ------------------------------------------------------------------
_mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=MagicMock())


# ------------------------------------------------------------------
# homeassistant.helpers.device_registry
# ------------------------------------------------------------------
class _DeviceInfo(dict):
    """Typed DeviceInfo — behaves like a dict so HA accepts it."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

_mod("homeassistant.helpers.device_registry", DeviceInfo=_DeviceInfo)


# ------------------------------------------------------------------
# homeassistant.helpers.entity_platform
# ------------------------------------------------------------------
_mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)


# ------------------------------------------------------------------
# homeassistant.helpers.entity
# ------------------------------------------------------------------
_mod("homeassistant.helpers.entity", DeviceInfo=_DeviceInfo)


# ------------------------------------------------------------------
# homeassistant.helpers.selector
# ------------------------------------------------------------------
class _SelectOptionDict(dict):
    def __init__(self, *, value, label):
        super().__init__(value=value, label=label)

class _SelectSelectorConfig:
    def __init__(self, *, options, multiple=False):
        self.options = options
        self.multiple = multiple

class _SelectSelector:
    def __init__(self, config):
        self.config = config

_mod(
    "homeassistant.helpers.selector",
    SelectOptionDict=_SelectOptionDict,
    SelectSelector=_SelectSelector,
    SelectSelectorConfig=_SelectSelectorConfig,
)


# ------------------------------------------------------------------
# homeassistant.components.sensor
# ------------------------------------------------------------------
class _SensorEntity:
    pass

class _SensorDeviceClass:
    TIMESTAMP = "timestamp"

_mod(
    "homeassistant.components.sensor",
    SensorEntity=_SensorEntity,
    SensorDeviceClass=_SensorDeviceClass,
)


# ------------------------------------------------------------------
# voluptuous  (already installed as a real package, but mock it anyway
#              so tests don't need to depend on its schema validation)
# ------------------------------------------------------------------
if "voluptuous" not in sys.modules:
    import unittest.mock as _um
    _vol_mod = types.ModuleType("voluptuous")
    # Make vol.Schema(...) and vol.Required(...) etc. just pass through
    _vol_mod.Schema = lambda s, **kw: s
    _vol_mod.Required = lambda k, **kw: k
    _vol_mod.Optional = lambda k, **kw: k
    _vol_mod.All = lambda *a, **kw: a[0] if a else None
    _vol_mod.In = lambda v: v
    _vol_mod.Range = lambda **kw: None
    _vol_mod.Length = lambda **kw: None
    sys.modules["voluptuous"] = _vol_mod
