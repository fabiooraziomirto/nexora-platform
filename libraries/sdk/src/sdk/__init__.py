"""
Python SDK for Nxr v2.0

This SDK provides client libraries for interacting with Nxr services
via REST API and gRPC.
"""

__version__ = "0.1.0"

from sdk.api.client import NxrClient
from sdk.api.devices import DeviceClient
from sdk.api.fleet import FleetClient
from sdk.api.network import NetworkClient
from sdk.api.execution import ExecutionClient
from sdk.grpc.client import NxrGRPCClient
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
    "NxrClient",
    "DeviceClient",
    "FleetClient",
    "NetworkClient",
    "ExecutionClient",
    "NxrGRPCClient",
    "Device",
    "DeviceStatus",
    "Fleet",
    "Network",
    "Execution",
    "ExecutionStatus",
    "PaginatedResponse",
]

