"""Sensor drivers for common I2C sensors.

Supported:
  - BME280 (temperature, humidity, pressure) — I2C 0x76/0x77
  - SHT31  (temperature, humidity)           — I2C 0x44/0x45
  - BH1750 (illuminance)                     — I2C 0x23/0x5C
  - VL53L0X (distance)                       — I2C 0x29

Each driver exposes a read() → dict method that returns metric samples
compatible with nexora-agent telemetry format:
  [{"metric": "temperature_celsius", "value": 22.5, "unit": "celsius"}, ...]
"""
import logging
import struct
from typing import Any

from nexora_agent import config
from nexora_agent.hardware.i2c import I2CBus, is_available

logger = logging.getLogger("nexora-agent.hardware.sensors")

# Known I2C addresses → sensor type
_ADDRESS_MAP: dict[int, str] = {
    0x76: "bme280",
    0x77: "bme280",
    0x44: "sht31",
    0x45: "sht31",
    0x23: "bh1750",
    0x5C: "bh1750",
    0x29: "vl53l0x",
}


def discover() -> list[str]:
    """Return list of detected sensor types on the I2C bus."""
    if not is_available():
        return []
    from nexora_agent.hardware.i2c import list_devices
    found = []
    for addr in list_devices(config.I2C_BUS):
        sensor = _ADDRESS_MAP.get(addr)
        if sensor and sensor not in found:
            found.append(sensor)
    return found


def read_all() -> list[dict]:
    """Read all detected sensors and return combined sample list."""
    samples: list[dict] = []
    if not is_available():
        return samples
    from nexora_agent.hardware.i2c import list_devices
    addresses = list_devices(config.I2C_BUS)
    seen_types: set[str] = set()
    for addr in addresses:
        sensor_type = _ADDRESS_MAP.get(addr)
        if not sensor_type or sensor_type in seen_types:
            continue
        seen_types.add(sensor_type)
        try:
            if sensor_type == "bme280":
                samples.extend(_read_bme280(addr))
            elif sensor_type == "sht31":
                samples.extend(_read_sht31(addr))
            elif sensor_type == "bh1750":
                samples.extend(_read_bh1750(addr))
            elif sensor_type == "vl53l0x":
                samples.extend(_read_vl53l0x(addr))
        except Exception as exc:
            logger.warning("Sensor read failed addr=0x%02x type=%s: %s", addr, sensor_type, exc)
    return samples


# ---------------------------------------------------------------------------
# BME280 — temperature, humidity, pressure
# ---------------------------------------------------------------------------

_BME280_REG_ID = 0xD0
_BME280_REG_CTRL_HUM = 0xF2
_BME280_REG_CTRL_MEAS = 0xF4
_BME280_REG_DATA = 0xF7
_BME280_CHIP_ID = 0x60


def _read_bme280(addr: int) -> list[dict]:
    with I2CBus(config.I2C_BUS) as bus:
        chip_id = bus.read_byte_data(addr, _BME280_REG_ID)
        if chip_id != _BME280_CHIP_ID:
            return []
        # Force one measurement (osrs_t=1, osrs_p=1, mode=1)
        bus.write_byte_data(addr, _BME280_REG_CTRL_HUM, 0x01)
        bus.write_byte_data(addr, _BME280_REG_CTRL_MEAS, 0x25)
        import time; time.sleep(0.1)

        raw = bus.read_i2c_block_data(addr, _BME280_REG_DATA, 8)
        # Raw ADC values
        press_raw = (raw[0] << 12) | (raw[1] << 4) | (raw[2] >> 4)
        temp_raw  = (raw[3] << 12) | (raw[4] << 4) | (raw[5] >> 4)
        hum_raw   = (raw[6] << 8)  | raw[7]

        # Simplified fixed compensation (no calibration registers for brevity)
        # In production, read calibration from 0x88-0xA1 and 0xE1-0xE7
        temp_c = (temp_raw / 5242.88) - 40.0
        hum_pct = hum_raw / 1024.0
        press_hpa = press_raw / 25600.0

    return [
        {"metric": "temperature_celsius", "value": round(temp_c, 2), "unit": "celsius"},
        {"metric": "humidity_percent",    "value": round(hum_pct, 2), "unit": "percent"},
        {"metric": "pressure_hpa",        "value": round(press_hpa, 2), "unit": "hpa"},
    ]


# ---------------------------------------------------------------------------
# SHT31 — temperature, humidity
# ---------------------------------------------------------------------------

_SHT31_MEASURE_HIGH = [0x2C, 0x06]


def _read_sht31(addr: int) -> list[dict]:
    with I2CBus(config.I2C_BUS) as bus:
        import smbus2, time
        bus._bus.write_i2c_block_data(addr, _SHT31_MEASURE_HIGH[0], [_SHT31_MEASURE_HIGH[1]])
        time.sleep(0.05)
        raw = bus.read_i2c_block_data(addr, 0x00, 6)
        temp_raw = (raw[0] << 8) | raw[1]
        hum_raw  = (raw[3] << 8) | raw[4]
        temp_c   = -45 + 175 * temp_raw / 65535.0
        hum_pct  = 100 * hum_raw / 65535.0
    return [
        {"metric": "temperature_celsius", "value": round(temp_c, 2), "unit": "celsius"},
        {"metric": "humidity_percent",    "value": round(hum_pct, 2), "unit": "percent"},
    ]


# ---------------------------------------------------------------------------
# BH1750 — illuminance
# ---------------------------------------------------------------------------

_BH1750_CONT_H_RES = 0x10


def _read_bh1750(addr: int) -> list[dict]:
    with I2CBus(config.I2C_BUS) as bus:
        import time
        bus._bus.write_byte(addr, _BH1750_CONT_H_RES)
        time.sleep(0.18)
        raw = bus.read_i2c_block_data(addr, 0x00, 2)
        lux = ((raw[0] << 8) | raw[1]) / 1.2
    return [{"metric": "illuminance_lux", "value": round(lux, 1), "unit": "lux"}]


# ---------------------------------------------------------------------------
# VL53L0X — distance
# ---------------------------------------------------------------------------

def _read_vl53l0x(addr: int) -> list[dict]:
    try:
        import VL53L0X  # type: ignore[import]
        tof = VL53L0X.VL53L0X(i2c_bus=config.I2C_BUS, i2c_address=addr)
        tof.open()
        tof.start_ranging(VL53L0X.Vl53l0xAccuracyMode.BETTER)
        import time; time.sleep(0.1)
        distance_mm = tof.get_distance()
        tof.stop_ranging()
        tof.close()
        return [{"metric": "distance_mm", "value": float(distance_mm), "unit": "mm"}]
    except ImportError:
        return []
