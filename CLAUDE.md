# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Moen Smart Water Network devices (smart irrigation controllers). The integration communicates with Moen's IoT API and uses AWS IoT for real-time device state updates via MQTT shadow messages.

## Key Architecture Components

- **Custom Component Structure**: Located in `custom_components/moen_smart_water_network/`
- **API Client**: Handles authentication with Moen's OAuth2 API and AWS IoT MQTT subscriptions
- **Data Coordinator**: Manages device state updates both via polling and real-time MQTT messages
- **Entity Types**: Supports sensors, binary sensors, and switches for irrigation zones and device status
- **AWS Integration**: Uses AWS IoT Device Shadow for real-time state synchronization

## Development Commands

### Setup and Installation

```bash
# Install dependencies
./scripts/setup

# Development setup (starts Home Assistant in debug mode)
./scripts/develop
```

### Code Quality

```bash
# Run linter (uses ruff)
./scripts/lint

# Run tests
pytest

# Run specific test file
pytest tests/test_sensors.py
```

### Home Assistant Testing

The integration includes a full Home Assistant development environment:

- Config directory: `config/` with `configuration.yaml`
- Custom component is automatically loaded via PYTHONPATH in develop script
- Debug logging enabled for the integration in `config/configuration.yaml`

## Authentication flow

The integration uses Moen's OAuth2 API with JWT tokens and AWS Cognito for IoT access:

1. Access/refresh tokens from OAuth2 flow
2. JWT token validation for AWS Cognito identity
3. MQTT connection to AWS IoT using Cognito credentials

## Real-time updates

The integration subscribes to AWS IoT Device Shadow updates for real-time state changes:

- Shadow messages merged into coordinator state
- Automatic listener updates trigger entity state refreshes
- Fallback to polling every 15 seconds for device information

## Dependencies

### Runtime

- `awsiotsdk` - AWS IoT Device SDK for MQTT communication
- `awscrt` - AWS Common Runtime for authentication

### Development

- `ruff` - Linter and formatter
- `pytest` + `pytest-homeassistant-custom-component`
- `mypy` - Type checking

## Configuration

Integration configured via Home Assistant UI (config flow). Requires:

- Access token from Moen OAuth2 flow
- Refresh token for token renewal
- Device client IDs for MQTT subscriptions

Home Assistant coding patterns and conventions are in CLAUDE_HASS.md.
