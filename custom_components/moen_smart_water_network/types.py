"""Type definitions for Moen Smart Water Network API responses."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class LocationData(TypedDict):
    """Location information."""

    id: str


class ConnectivityData(TypedDict):
    """Device connectivity information."""

    type: str
    net: str
    rssi: int


class FirmwareData(TypedDict):
    """Device firmware information."""

    version: str
    upgradeUri: str


class WateringStateData(TypedDict):
    """Current watering state."""

    running: bool


class RainSensorData(TypedDict):
    """Rain sensor configuration."""

    connected: bool
    type: str


class FlowSensorData(TypedDict):
    """Flow sensor configuration."""

    connected: bool
    unit: str
    kFactor: int
    offset: int
    galPerPulse: int
    lPerPulse: float
    mLPerPulse: float


class ZoneData(TypedDict):
    """Individual irrigation zone data."""

    id: str
    clientId: str
    wired: bool
    media: list[Any]
    auditStatus: Literal["normal", "fault", "noaudit"]
    auditEnabled: bool
    fault: str | None  # Optional, present when auditStatus is "fault"
    type: str
    soilType: str
    sunExposure: str
    sprinklerHead: str
    slope: str
    voiceDurSec: int
    flowMaxThresh: float
    flowMinThresh: float
    soakDelay: int
    soakRun: int
    soilLogic: str
    name: str
    enabled: bool
    systemEfficiency: float
    numberHeads: int
    cropCoefficient: float
    connected: bool
    area: float
    sprinklerHeadRate: float
    skipOnRainSensor: bool
    # Optional fields for specific zones
    allowableWaterContent: float | None
    managementAllowedDepletion: int | None
    rootDepth: int | None


class IrrigationData(TypedDict):
    """Irrigation system information."""

    lastAuditDate: str
    numZones: int
    wateringState: WateringStateData
    masterValveConnected: bool
    wateringMode: str
    seasonalAdjust: list[int]
    rainSensor: RainSensorData
    flowSensor: FlowSensorData
    zones: list[ZoneData]
    soilSensors: list[Any]


class DeviceData(TypedDict):
    """Complete device data from Moen API."""

    duid: str
    clientId: str
    nickname: str
    type: str
    location: LocationData
    connected: bool
    lastConnect: str
    isDevDevice: bool
    connectivity: ConnectivityData
    firmware: FirmwareData
    powerSource: str
    irrigation: IrrigationData


class UserData(TypedDict):
    """User data from API."""

    legacyId: str


class TokenData(TypedDict):
    """OAuth token data."""

    access_token: str
    expires_in: int
    id_token: str


class AuthResponse(TypedDict):
    """OAuth refresh response."""

    token: TokenData


class ManualRunZoneData(TypedDict):
    """Zone data for manual run requests."""

    dur: int  # Duration in seconds


class ManualRunData(TypedDict):
    """Manual run request data."""

    duid: str
    ttl: int
    zones: dict[str, ManualRunZoneData]
    name: str


class ZoneEnableData(TypedDict):
    """Zone enable/disable request data."""

    enabled: bool


class AppShadowRequestBody(TypedDict):
    """App shadow request body."""

    shadow: bool
    locale: str
    clientId: str


class AppShadowRequest(TypedDict):
    """App shadow lambda invocation request."""

    escape: bool
    parse: bool
    fn: str
    body: AppShadowRequestBody


class ScheduleZoneData(TypedDict):
    """Schedule zone configuration."""

    duration: int
    seasonalAdjust: bool
    id: str
    clientId: int
    smartAdjust: Literal["none", "weather"]


class PreferredTimeData(TypedDict, total=False):
    """Schedule preferred time configuration."""

    startAt: str  # Can be time like "13:00:00" or special value like "dawn"
    endBefore: str  # Can be time like "06:00:00" or special value like "dawn"


class ScheduleData(TypedDict):
    """Individual irrigation schedule data."""

    id: str
    name: str
    duid: str
    status: Literal["active", "inactive"]
    frequency: Literal["daily", "weekly", "even"]
    zones: list[ScheduleZoneData]
    startDate: str
    preferredTime: PreferredTimeData
    createdAt: str
    modifiedAt: str
    cycleSoak: bool
    waterSense: bool
    seasonalAdjust: bool
    ignoreSkipReason: bool
    ignoreSoilSensorSkip: bool
    type: str
    # Optional fields for weekly schedules
    daysOfWeek: list[str] | None


class SchedulesResponse(TypedDict):
    """Response from schedules API endpoint."""

    items: list[ScheduleData]
    total: int
    params: dict[str, Any]


class DevicesResponse(TypedDict):
    """Response from devices API endpoint."""

    count: int
    devices: list[DeviceData]
    params: dict[str, Any]
    total: int


class CoordinatorData(TypedDict):
    """Data structure returned by MoenDataUpdateCoordinator."""

    device: DeviceData
    schedules: dict[str, ScheduleData]
