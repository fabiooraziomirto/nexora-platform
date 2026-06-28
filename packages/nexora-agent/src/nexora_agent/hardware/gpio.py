"""GPIO abstraction for nexora-agent.

Uses gpiozero when available (RPi + Linux GPIO chips via lgpio/pigpio).
Falls back to a no-op stub so the agent starts on non-GPIO hardware.
"""
import logging
from typing import Callable

logger = logging.getLogger("nexora-agent.hardware.gpio")

_AVAILABLE = False
try:
    from gpiozero import LED, Button, OutputDevice, InputDevice  # noqa: F401
    _AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    return _AVAILABLE


class DigitalOutput:
    """Controls a digital output pin (LED, relay, etc.)."""

    def __init__(self, pin: int, active_high: bool = True, initial: bool = False):
        self._pin = pin
        if _AVAILABLE:
            from gpiozero import OutputDevice
            self._dev = OutputDevice(pin, active_high=active_high, initial_value=initial)
        else:
            self._dev = None
            self._state = initial
            logger.warning("GPIO not available — pin %d is a stub", pin)

    def on(self) -> None:
        if self._dev:
            self._dev.on()
        else:
            self._state = True

    def off(self) -> None:
        if self._dev:
            self._dev.off()
        else:
            self._state = False

    def toggle(self) -> None:
        if self._dev:
            self._dev.toggle()
        else:
            self._state = not self._state

    @property
    def value(self) -> bool:
        if self._dev:
            return bool(self._dev.value)
        return self._state

    def close(self) -> None:
        if self._dev:
            self._dev.close()


class DigitalInput:
    """Reads a digital input pin (button, PIR, etc.)."""

    def __init__(self, pin: int, pull_up: bool = True, on_press: Callable | None = None):
        self._pin = pin
        if _AVAILABLE:
            from gpiozero import Button
            self._dev = Button(pin, pull_up=pull_up)
            if on_press:
                self._dev.when_pressed = on_press
        else:
            self._dev = None
            logger.warning("GPIO not available — pin %d input is a stub", pin)

    @property
    def is_pressed(self) -> bool:
        if self._dev:
            return self._dev.is_pressed
        return False

    def close(self) -> None:
        if self._dev:
            self._dev.close()
