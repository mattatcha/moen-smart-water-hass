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


class IrrigationWateringStateData(TypedDict):
    """Current watering state."""

    running: bool


class IrrigationRainSensorData(TypedDict):
    """Rain sensor configuration."""

    connected: bool
    type: str


class IrrigationFlowSensorData(TypedDict):
    """Sprinkler controller flow sensor configuration."""

    connected: bool
    unit: str
    kFactor: int
    offset: int
    galPerPulse: int
    lPerPulse: float
    mLPerPulse: float


class IrrigationZoneData(TypedDict):
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
    wateringState: IrrigationWateringStateData
    masterValveConnected: bool
    wateringMode: str
    seasonalAdjust: list[int]
    rainSensor: IrrigationRainSensorData
    flowSensor: IrrigationFlowSensorData
    zones: list[IrrigationZoneData]
    soilSensors: list[Any]


class DeviceData(TypedDict, total=False):
    """
    Device data from the Moen v3 API.

    Which keys are present depends on the device type: only ``hyd`` devices
    have ``irrigation``, and ``flo`` devices have no ``firmware`` or
    ``connected``.
    """

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


class IrrigationZoneDuration(TypedDict):
    """Zone duration for manual plan requests (APK format)."""

    id: str
    duration: int  # seconds


class IrrigationManualRunZoneData(TypedDict):
    """Zone data for legacy manual run requests."""

    dur: int


class IrrigationManualRunData(TypedDict):
    """Manual run request data."""

    duid: str
    ttl: int
    zones: dict[str, IrrigationManualRunZoneData]
    name: str


class IrrigationZoneEnableData(TypedDict):
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


class IrrigationScheduleZoneData(TypedDict):
    """Schedule zone configuration."""

    duration: int
    seasonalAdjust: bool
    id: str
    clientId: int
    smartAdjust: Literal["none", "weather"]


class IrrigationPreferredTimeData(TypedDict, total=False):
    """Schedule preferred time configuration."""

    startAt: str
    endBefore: str


class IrrigationScheduleData(TypedDict):
    """Individual irrigation schedule data."""

    id: str
    name: str
    duid: str
    status: Literal["active", "inactive"]
    frequency: Literal["daily", "weekly", "even", "odd"]
    zones: list[IrrigationScheduleZoneData]
    startDate: str
    preferredTime: IrrigationPreferredTimeData
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


class IrrigationSchedulesResponse(TypedDict):
    """Response from schedules API endpoint."""

    items: list[IrrigationScheduleData]
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


class IrrigationCoordinatorData(TypedDict):
    """Data returned by MoenIrrigationCoordinator."""

    device: DeviceData
    schedules: dict[str, IrrigationScheduleData]


# --- Sump pump monitor (type "nab"), shapes as observed from the live API ---


class SumpPumpDroplet(TypedDict, total=False):
    """Water level state; only populated while the device is streaming."""

    level: int  # -1 when not streaming; no unit is published
    trend: str  # e.g. "stable"
    floodRisk: str  # "unknown" when not streaming, e.g. "normal"
    primaryState: str  # "unknown" when not streaming, e.g. "operational"
    backupState: str  # "unknown" when not streaming, e.g. "operational"


class SumpPumpBackupTestResult(TypedDict, total=False):
    """Result of the last backup pump test."""

    status: str  # "none" when never run
    timestamp: str  # ISO 8601; epoch 0 when never run


class SumpPumpReportedState(TypedDict, total=False):
    """Fields seen in a sump pump monitor's shadow ``state.reported``."""

    connected: bool
    wifiNetwork: str
    wifiRssi: int
    firmwareVersion: str
    powerSource: str  # "ac" on mains power
    batteryPercentage: int
    batteryLifeRemaining: int
    systemState: str
    crockState: str
    crockBackup: str
    crockDiameterMM: int
    crockBckTst: str  # backup test schedule; "none" = testing disabled
    bckTstResults: SumpPumpBackupTestResult
    droplet: SumpPumpDroplet
    crockTofDistance: int
    beeperPiezoEnable: bool
    beeperSirenEnable: bool
    tempLowThreshold: float  # degrees Celsius
    tempHighThreshold: float  # degrees Celsius
    humidLowThreshold: float
    humidHighThreshold: float
    lastConnect: int  # epoch milliseconds


class ShadowState(TypedDict, total=False):
    """AWS IoT shadow ``state`` block."""

    reported: dict[str, Any]
    desired: dict[str, Any]
    delta: dict[str, Any]


class ShadowDocument(TypedDict, total=False):
    """AWS IoT shadow document returned by the shadow-get Lambda."""

    state: ShadowState
    metadata: dict[str, Any]
    version: int
    timestamp: int


class SumpPumpEnvironmentReading(TypedDict, total=False):
    """One environment reading; thresholds are in ``unitOfMeasure``."""

    unitOfMeasure: str  # "F" or "percent"
    current: float
    low: float  # gauge minimum
    high: float  # gauge maximum
    tempLowThreshold: float
    tempHighThreshold: float
    humidLowThreshold: float
    humidHighThreshold: float


class SumpPumpEnvironment(TypedDict, total=False):
    """Latest temperature and humidity."""

    tempData: SumpPumpEnvironmentReading
    humidData: SumpPumpEnvironmentReading


class SumpPumpLastUsage(TypedDict, total=False):
    """Last pump cycle summary; empty when the device has no cycles."""

    duid: str
    lastOutgoTime: str  # ISO 8601, when the last pump-out cycle happened
    backupUsed: bool
    estimatedNextRun: str  # ISO 8601
    estimatedTimeUntilNextRunMS: int


class SumpPumpSession(TypedDict, total=False):
    """One pump cycle (app History card)."""

    date: str  # ISO 8601
    fillVolume: float  # "Water In" rate
    fillVolumeUnits: str  # "gpm"
    fillTimeMS: int  # "Water In" duration
    emptyVolume: float  # "Water Out" volume
    emptyVolumeUnits: str  # "gallons"
    emptyTimeMS: int  # "Water Out" duration (pump run time)
    backupRan: bool


class SumpPumpCapacityDay(TypedDict, total=False):
    """One of the primary pump's highest capacity days."""

    day: str  # ISO 8601
    capacity: int  # percent
    warnColor: str


class SumpPumpCapacity(TypedDict, total=False):
    """Primary pump capacity assessment (app "Pump Capacity" card)."""

    TopTen: list[SumpPumpCapacityDay]
    pumpSize: int
    pumpIndicator: str  # e.g. "undersized_capacity"
    pumpCapacitySufficient: bool


class ActiveAlert(TypedDict, total=False):
    """An active alert from the v2 alerts Lambda."""

    id: str
    duid: str  # numeric clientId as a string
    time: str
    state: str  # e.g. "active_unlack_unrack_unsuppressed"
    severity: str
    title: str
    text: str
    dismiss: bool
    silence: bool


class SumpPumpCoordinatorData(TypedDict):
    """Data structure returned by MoenSumpPumpCoordinator."""

    device: DeviceData
    shadow: dict[str, Any]  # shadow state.reported
    environment: SumpPumpEnvironment
    last_usage: SumpPumpLastUsage
    last_session: SumpPumpSession | None
    capacity: SumpPumpCapacity
    alerts: list[ActiveAlert]
