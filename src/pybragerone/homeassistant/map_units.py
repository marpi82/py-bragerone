"""Module src/pybragerone/homeassistant/map_units.py."""
# src/pybragerone/homeassistant/map_units.py
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Home Assistant constants:
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfLength,
    UnitOfMass,
    # (jeśli masz: UnitOfSpeed, UnitOfVolumeFlowRate itd. - dołóż zależnie od wersji HA)
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)


# minimalna normalizacja
def _norm(label: str) -> str:
    """Norm.
    
    Args:
    label: TODO.

    Returns:
    TODO.
    """
    s = label.strip().lower()
    s = s.replace("°", "deg")
    s = s.replace("⋅", "*").replace("·", "*")
    s = s.replace("³", "3").replace("^3", "3")
    s = s.replace("²", "2").replace("^2", "2")
    s = re.sub(r"\s+", "", s)
    return s

# baza najczęstszych mapowań na HA
_M: dict[str, str] = {
    # temperatura
    "degc": UnitOfTemperature.CELSIUS,
    "c": UnitOfTemperature.CELSIUS,
    "°c": UnitOfTemperature.CELSIUS,  # gdyby przeszło nienormalizowane

    "degf": UnitOfTemperature.FAHRENHEIT,
    "f": UnitOfTemperature.FAHRENHEIT,
    "°f": UnitOfTemperature.FAHRENHEIT,

    # procent
    "%": PERCENTAGE,
    "percent": PERCENTAGE,
    "percentage": PERCENTAGE,

    # czas
    "s": UnitOfTime.SECONDS,
    "sec": UnitOfTime.SECONDS,
    "secs": UnitOfTime.SECONDS,
    "second": UnitOfTime.SECONDS,
    "seconds": UnitOfTime.SECONDS,

    "min": UnitOfTime.MINUTES,
    "mins": UnitOfTime.MINUTES,
    "minute": UnitOfTime.MINUTES,
    "minutes": UnitOfTime.MINUTES,

    "h": UnitOfTime.HOURS,
    "hr": UnitOfTime.HOURS,
    "hrs": UnitOfTime.HOURS,
    "hour": UnitOfTime.HOURS,
    "hours": UnitOfTime.HOURS,

    # energia / moc
    "wh": UnitOfEnergy.WATT_HOUR,
    "kwh": UnitOfEnergy.KILO_WATT_HOUR,
    "w": UnitOfPower.WATT,
    "kw": UnitOfPower.KILO_WATT,

    # elektryka
    "v": UnitOfElectricPotential.VOLT,
    "volt": UnitOfElectricPotential.VOLT,
    "a": UnitOfElectricCurrent.AMPERE,
    "amp": UnitOfElectricCurrent.AMPERE,
    "amps": UnitOfElectricCurrent.AMPERE,
    "hz": UnitOfFrequency.HERTZ,

    # ciśnienie
    "pa": UnitOfPressure.PA,
    "hpa": UnitOfPressure.HPA,
    "mbar": UnitOfPressure.MBAR,
    "bar": UnitOfPressure.BAR,

    # długość/objętość/masa (najczęstsze)
    "mm": UnitOfLength.MILLIMETERS,
    "cm": UnitOfLength.CENTIMETERS,
    "m": UnitOfLength.METERS,

    "l": UnitOfVolume.LITERS,
    "ml": UnitOfVolume.MILLILITERS,
    "m3": UnitOfVolume.CUBIC_METERS,

    "g": UnitOfMass.GRAMS,
    "kg": UnitOfMass.KILOGRAMS,

    # przykłady z indeksami/pochodnymi (często w HVAC)
    "l/h": "L/h",          # HA nie ma stałej, zostaw jako string sensowny dla UI
    "m3/h": "m³/h",        # brak stałej - zwracamy symbol
    "kw/m2": "kW/m²",      # jw.
}

def resolve_ha_unit(u: Any, units_i18n: Mapping[str, str] | None = None) -> str | None:
    """Zamień `u` (int lub str lub None) na stałą Home Assistant.
    - Jeśli `u` to int -> spróbuj units_i18n[str(u)] -> etykieta -> mapuj.
    - Jeśli `u` to str -> mapuj bezpośrednio (po normalizacji).
    - Jeśli brak mapowania -> zwróć oryginalną etykietę (jako zwykły tekst) lub None.
    """
    if u is None:
        return None

    # z surowego kodu (np. 1 -> "°C")
    if isinstance(u, int):
        label = str(u)
        if units_i18n:
            label = units_i18n.get(str(u), str(u))
        # jeśli nie znaleziono tłumaczenia, zostaw „1” (mało sensowne) lub zwróć None
        if label.isdigit():  # nic nie wiemy
            return None
        norm = _norm(label)
        return _M.get(norm, label)

    # ze stringa (np. "%", "°C", "kWh")
    if isinstance(u, str):
        norm = _norm(u)
        # proste trafienie w słownik
        if norm in _M:
            return _M[norm]
        # fallback: często wystarczy upper-case (np. "kWh" przejdzie jako "kWh")
        return u

    # nieznany typ
    return None
