"""
gRPC package entrypoint.

Proto stubs can be generated under sdk.grpc.proto in a later phase.
Current client exposes an HTTP fallback-compatible interface.
"""

from sdk.grpc.client import NxrGRPCClient

__all__ = ["NxrGRPCClient"]
