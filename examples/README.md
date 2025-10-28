# Examples

This directory contains working examples for the pybragerone library.
All examples are referenced in the documentation.

## Available Examples

### Basic Usage

- `basic_login.py` - Simple login and device listing
- `read_parameters.py` - Fetch and display parameters
- `realtime_updates.py` - WebSocket real-time monitoring
- `paramstore_usage.py` - Using ParamStore for state management

### Advanced

- `gateway_setup.py` - Complete Gateway setup with error handling
- `ha_config_flow.py` - Home Assistant config flow pattern (asset-aware mode)
- `ha_runtime.py` - Home Assistant runtime pattern (lightweight mode)

## Running Examples

All examples require valid BragerOne credentials:

```bash
# Set credentials as environment variables
export PYBO_EMAIL="user@example.com"
export PYBO_PASSWORD="your-password"

# Run an example
python examples/basic_login.py
```

Or pass credentials directly:

```bash
python examples/basic_login.py --email user@example.com --password "***"
```

## Documentation

These examples are documented in:

- [Quick Start Tutorial](../docs/guides/quickstart.rst)
- [Quick Reference](../docs/reference/core_components.rst)
- [Architecture Guide](../docs/architecture/overview.rst)
