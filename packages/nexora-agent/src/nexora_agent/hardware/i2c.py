"""I2C bus helper for nexora-agent.

Wraps smbus2 with a graceful stub when the library or bus is unavailable
(e.g. on a development machine without /dev/i2c-*).
"""
import logging
from typing import Any

logger = logging.getLogger("nexora-agent.hardware.i2c")

_AVAILABLE = False
try:
    import smbus2  # noqa: F401
    _AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    return _AVAILABLE


def list_devices(bus_number: int = 1) -> list[int]:
    """Scan the I2C bus and return a list of responding addresses."""
    if not _AVAILABLE:
        return []
    import smbus2
    found = []
    try:
        with smbus2.SMBus(bus_number) as bus:
            for addr in range(0x03, 0x78):
                try:
                    bus.read_byte(addr)
                    found.append(addr)
                except OSError:
                    pass
    except Exception as exc:
        logger.debug("I2C scan failed on bus %d: %s", bus_number, exc)
    return found


class I2CBus:
    """Context manager around a smbus2.SMBus instance."""

    def __init__(self, bus_number: int = 1):
        self._bus_number = bus_number
        self._bus: Any = None

    def __enter__(self):
        if _AVAILABLE:
            import smbus2
            self._bus = smbus2.SMBus(self._bus_number)
        return self

    def __exit__(self, *_):
        if self._bus:
            self._bus.close()

    def read_byte_data(self, addr: int, register: int) -> int:
        if not self._bus:
            return 0
        return self._bus.read_byte_data(addr, register)

    def read_i2c_block_data(self, addr: int, register: int, length: int) -> list[int]:
        if not self._bus:
            return [0] * length
        return self._bus.read_i2c_block_data(addr, register, length)

    def write_byte_data(self, addr: int, register: int, value: int) -> None:
        if self._bus:
            self._bus.write_byte_data(addr, register, value)
