"""Type definitions for Moen Smart Water Network API responses."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# --- Device data ---


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
    fault: str | None
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


# --- User / auth ---


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


# --- Request types ---


class ZoneDuration(TypedDict):
    """Zone duration for manual plan requests (APK format)."""

    id: str
    duration: int  # seconds


class ManualRunZoneData(TypedDict):
    """Zone data for legacy manual run requests."""

    dur: int


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


# --- Schedule types ---


class ScheduleZoneData(TypedDict):
    """Schedule zone configuration."""

    duration: int
    seasonalAdjust: bool
    id: str
    clientId: int
    smartAdjust: Literal["none", "weather"]


class PreferredTimeData(TypedDict, total=False):
    """Schedule preferred time configuration."""

    startAt: str
    endBefore: str


class ScheduleData(TypedDict):
    """Individual irrigation schedule data."""

    id: str
    name: str
    duid: str
    status: Literal["active", "inactive"]
    frequency: Literal["daily", "weekly", "even", "odd"]
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
    daysOfWeek: list[str] | None


# --- Response types ---


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


# --- Irrigation run messages (from /async/{DUID} MQTT topic) ---

IrrigationRunStatus = Literal[
    "PAUSED", "WATERING", "SOAKING", "COMPLETED", "SKIPPED", "STARTING"
]


class IrrigationPlanned(TypedDict, total=False):
    """A planned zone in an irrigation run."""

    zoneId: str
    event: str
    isActive: bool
    seqNum: int
    duration: int
    durationRemaining: int
    ts: int


class IrrigationCompleted(TypedDict, total=False):
    """A completed zone in an irrigation run."""

    zoneId: str
    event: str
    status: str
    ts: int
    actualDuration: int
    plannedDuration: int


class IrrigationRunState(TypedDict, total=False):
    """State of an irrigation run."""

    status: IrrigationRunStatus
    completed: list[IrrigationCompleted]
    planned: list[IrrigationPlanned]


class IrrigationRunBody(TypedDict, total=False):
    """Body of an irrigation run message."""

    id: str
    state: IrrigationRunState


class IrrigationRunMessage(TypedDict, total=False):
    """Message received on /async/{DUID} topic for irrigation run updates."""

    ts: int
    event: str
    body: IrrigationRunBody


# --- Coordinator data ---


class CoordinatorData(TypedDict):
    """Data structure returned by MoenDataUpdateCoordinator."""

    device: DeviceData
    schedules: dict[str, ScheduleData]
