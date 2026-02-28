# Home Assistant custom integration guidelines

This repository is a Home Assistant custom integration, not the HA core. These guidelines are adapted from HA core standards for custom component development.

## Python requirements

- **Compatibility**: Python 3.13+
- **Language features**: Use the newest features when possible (pattern matching, type hints, f-strings, dataclasses, walrus operator)

## Code quality standards

- **Formatting/linting**: Ruff (`./scripts/lint`)
- **Type checking**: MyPy
- **Testing**: pytest with `pytest-homeassistant-custom-component`
- **Language**: American English, sentence case

### Documentation standards

- **File headers**: Short and concise
  ```python
  """Integration for Moen Smart Water Network."""
  ```
- **Method/function docstrings**: Required for all public methods
- **Comments**: Explain "why" not "what", keep lines under 80 characters when possible

### Logging

- No periods at end of messages
- No integration names/domains (added automatically)
- No sensitive data (keys, tokens, passwords)
- Use debug level for non-user-facing messages
- **Lazy logging**:
  ```python
  _LOGGER.debug("This is a log message with %s", variable)
  ```

## Async programming

- All external I/O operations must be async
- Avoid sleeping in loops, awaiting in loops (use `gather` instead), and blocking calls
- Use `asyncio.sleep()` instead of `time.sleep()`
- Use executor for blocking I/O: `await hass.async_add_executor_job(blocking_function, args)`
- **`@callback` decorator** for event-loop-safe functions

## Integration structure

```
custom_components/moen_smart_water_network/
├── __init__.py          # Entry point with async_setup_entry
├── manifest.json        # Integration metadata and dependencies
├── const.py             # Domain and constants
├── config_flow.py       # UI configuration flow
├── coordinator.py       # Data update coordinator + MQTT handling
├── entity.py            # Base entity class
├── sensor.py            # Sensor platform
├── binary_sensor.py     # Binary sensor platform
├── switch.py            # Switch platform (zone controls)
├── diagnostics.py       # Diagnostic data collection
├── services.yaml        # Service definitions
├── strings.json         # User-facing text and translations
└── moen_api/            # API client library
    ├── __init__.py
    ├── auth.py           # OAuth2 + AWS Cognito authentication
    ├── client.py         # HTTP API client
    ├── mqtt.py           # AWS IoT MQTT shadow subscriptions
    ├── models.py         # Data models
    ├── const.py          # API constants
    └── exceptions.py     # Custom exceptions
```

## Key patterns

### Data update coordinator

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
            config_entry=config_entry,
        )

    async def _async_update_data(self):
        try:
            return await self.client.fetch_data()
        except ApiError as err:
            raise UpdateFailed(f"API communication error: {err}") from err
```

- Use `UpdateFailed` for API errors, `ConfigEntryAuthFailed` for auth issues
- Always pass `config_entry` parameter to coordinator

### Entity development

- **Unique IDs**: Required for every entity, use device serial numbers or stable identifiers (never IPs, hostnames, or names)
- **Entity naming**: Set `_attr_has_entity_name = True`, use `_attr_translation_key` for translatable names
- **Device classes**: Set appropriate `_attr_device_class` when available
- **Entity categories**: Use `EntityCategory.DIAGNOSTIC` for technical/system entities
- **State handling**: Use `None` for unknown values (not "unknown" or "unavailable")
- **Availability**: Implement `available` property instead of using "unavailable" state
- **Event subscriptions**: Subscribe in `async_added_to_hass` using `self.async_on_remove()`, never in `__init__`

### Device registry

```python
_attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, device.id)},
    name=device.name,
    manufacturer="Moen",
    model="Smart Water Network",
    sw_version=device.version,
)
```

### Config flow

- Store connection-critical config in `ConfigEntry.data`, non-critical settings in `ConfigEntry.options`
- Always validate user input and test connection during config flow
- Prevent duplicate configurations with `_abort_if_unique_id_configured()`

### Config entry unloading

```python
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### Diagnostics

- Always redact sensitive data (tokens, passwords, coordinates)
  ```python
  return async_redact_data(data, {"api_key", "password", "access_token", "refresh_token"})
  ```

## Error handling

- **Choose specific exceptions**: `ServiceValidationError`, `HomeAssistantError`, `ConfigEntryNotReady`, `ConfigEntryAuthFailed`, `ConfigEntryError`
- **Keep try blocks minimal** - process data outside the try/catch
- **Avoid bare exceptions** except in config flows and background tasks
- **Setup failure pattern**:
  ```python
  try:
      await device.async_setup()
  except (asyncio.TimeoutError, TimeoutException) as ex:
      raise ConfigEntryNotReady(f"Timeout connecting") from ex
  except AuthFailed as ex:
      raise ConfigEntryAuthFailed(f"Credentials expired") from ex
  ```

## Testing

- **Location**: `tests/`
- **Framework**: `pytest-homeassistant-custom-component`
- **Async mode**: `asyncio_mode = auto` (configured in `pytest.ini`)
- Mock all external dependencies (API calls, MQTT connections)
- Test through proper integration setup using fixtures, not direct entity construction
- Never access `hass.data` directly in tests

## Development commands

See `CLAUDE.md` for setup, lint, test, and develop commands.
