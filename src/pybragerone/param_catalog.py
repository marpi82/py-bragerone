"""
ParamCatalog - spójny widok:
- labels: mapowanie "PARAM_6" -> "Maksymalna wydajność dmuchawy"
- units: definicje jednostek (proste, enum itp.)
- meta: słowniki z PARAM_*.js (unit/command/min/max/value/status/componentType)
- param_units: mapowanie z runtime (po snapshotcie): (pool, id) -> unit_id (jako string)
- API pomocnicze: format_value, describe_param, pretty_param_key
"""

from __future__ import annotations

import re

from .types import JSON


class ParamCatalog:
    _UKEY_RE = re.compile(r"^(P\d+)\.u(\d+)$")

    def __init__(
        self,
        units: dict[str, JSON] | None = None,
        labels: dict[str, str] | None = None,
        meta: dict[str, JSON] | None = None,
    ) -> None:
        self.units: dict[str, JSON] = units or {}
        self.labels: dict[str, str] = labels or {}
        self.meta: dict[str, JSON] = meta or {}
        self.param_units: dict[tuple[str, int], str] = {}  # (pool, param_id) -> unit_id_str

    # --- new partial setters ---
    def set_units(self, units: dict[str, JSON] | None) -> None:
        self.units = units or {}

    def set_labels(self, labels: dict[str, str] | None) -> None:
        self.labels = labels or {}  # labels by param

    def set_meta(self, meta: dict[str, JSON] | None) -> None:
        self.meta = meta or {}  # meta by name

    # ---- runtime feed z Gateway (snapshot/ws) ----
    def touch_param_unit(self, pool: str, param_id: int, unit_id_str: str) -> None:
        self.param_units[(pool, param_id)] = unit_id_str

    # ---- etykiety ----
    def describe_param(self, param_id: int) -> str | None:
        key = f"PARAM_{param_id}"
        return self.labels.get(key)

    def pretty_param_key(self, pool: str, var: str) -> str:
        """
        Zamienia np. P6.v5 -> "PARAM_5" i zwraca 'parameters.PARAM_5' (name z meta),
        jeśli się da - inaczej klasyczny "pool.var".
        """
        if var and (
            var.startswith("v")
            or var.startswith("u")
            or var.startswith("s")
            or var.startswith("n")
            or var.startswith("x")
        ):
            try:
                pid = int(var[1:])
            except Exception:
                return f"{pool}.{var}"
            name = f"parameters.PARAM_{pid}"
            if name in self.meta:
                return name
            return f"parameters.PARAM_{pid}"
        return f"{pool}.{var}"

    # ---- formatowanie wartości ----
    def _lookup_unit(self, unit_id: str) -> JSON:
        return self.units.get(unit_id)

    def format_value(self, pool: str, var: str, value: object, lang: str | None = None) -> object:
        """
        value → ludzka forma:
        - jeśli to „uN” - nie formatujemy (to jest id jednostki)
        - jeśli enum (unit typ „enum”) → zwrot etykiety
        - jeśli zwykła jednostka (np. "°C") → f"{value} {unit}"
        - inaczej zwracamy surową wartość
        """
        if not isinstance(var, str):
            return value
        if var.startswith("u"):
            return value  # to jest id jednostki

        unit_id = None
        if var.startswith(("v", "n", "x", "s")):
            try:
                pid = int(var[1:])
            except Exception:
                pid = None
            if pid is not None:
                unit_id = self.param_units.get((pool, pid))  # runtime

        if unit_id is None:
            return value

        udef = self._lookup_unit(unit_id)
        if not isinstance(udef, dict):
            # prosta jednostka - string
            if isinstance(udef, str) and udef:
                return f"{value} {udef}"
            return value

        # enum?
        if "0" in udef:
            # enum-y mają klucze stringowe "0","1",...
            key = str(value)
            return udef.get(key, value)

        # zwykła jednostka (np. {"sym":"°C"} lub podobnie)
        sym = udef.get("sym") or udef.get("unit") or ""
        if sym:
            return f"{value} {sym}"
        return value

    def bind_units_from_snapshot(self, snapshot: dict[str, JSON]) -> int:
        """
        Przejdź po parach snapshotu i dla kluczy w formacie 'P<pool>.u<paramId>'
        dowiąż jednostkę do (pool, paramId), korzystając z już istniejącej mapy units.
        Zwraca liczbę powiązań.
        """
        if not snapshot:
            return 0

        bound = 0
        for full_key, unit_val in snapshot.items():
            m = self._UKEY_RE.match(full_key)
            if not m:
                continue
            pool = m.group(1)  # np. 'P6'
            try:
                param_id = int(m.group(2))
            except ValueError:
                continue

            # normalizuj jednostkę do str (w units mamy klucze tekstowe)
            unit_id_str = str(unit_val) if unit_val is not None else None
            if not unit_id_str:
                continue

            # istniejąca logika: zapamiętaj powiązanie
            try:
                self.touch_param_unit(pool, param_id, unit_id_str)
                bound += 1
            except Exception:
                # celowo „cicho” - jeżeli meta nie ma wpisu, po prostu pomijamy
                pass

        return bound
