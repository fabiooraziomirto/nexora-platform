"""
Python SDK for Stack4Things v2.0

This SDK provides client libraries for interacting with Stack4Things services
via REST API and gRPC.
"""

__version__ = "0.1.0"

from sdk.api.client import Stack4ThingsClient
from sdk.api.devices import DeviceClient
from sdk.api.fleet import FleetClient
from sdk.api.network import NetworkClient
from sdk.api.execution import ExecutionClient
from sdk.grpc.client import Stack4ThingsGRPCClient
from sdk.types import (
    Device,
    DeviceStatus,
    Fleet,
    Network,
    Execution,
    ExecutionStatus,
    PaginatedResponse,
)

__all__ = [
    "__version__",
    "Stack4ThingsClient",
    "DeviceClient",
    "FleetClient",
    "NetworkClient",
    "ExecutionClient",
    "Stack4ThingsGRPCClient",
    "Device",
    "DeviceStatus",
    "Fleet",
    "Network",
    "Execution",
    "ExecutionStatus",
    "PaginatedResponse",
]

