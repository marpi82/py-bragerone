from __future__ import annotations

from dataclasses import dataclass, field

from .labels import Labels
from .param_meta import ParamMeta
from .types import JSON, ParamId, ParamKey, Pool, UnitId
from .units import Units


@dataclass(slots=True)
class ParamCatalog:
    """In-memory view over labels/units/meta + runtime unit bindings."""

    labels: Labels = field(default_factory=Labels)
    units: Units = field(default_factory=Units)
    meta: ParamMeta = field(default_factory=ParamMeta)
    # runtime (pool, param) -> unit id
    param_units: dict[ParamKey, UnitId] = field(default_factory=dict)

    def set_labels(self, labels: Labels) -> None:
        self.labels = labels

    def set_units(self, units: Units) -> None:
        self.units = units

    def set_meta(self, meta: ParamMeta) -> None:
        self.meta = meta

    def touch_param_unit(self, pool: Pool, param_id: ParamId, unit_id: UnitId) -> None:
        self.param_units[(pool, param_id)] = unit_id

    def pretty_param_key(self, pool: Pool, var: str) -> str:
        """Return unified key name like 'parameters.PARAM_6' or 'pool.var' fallback."""
        if not var or var[0] not in "vunsx":
            return f"{pool}.{var}"
        try:
            pid = int(var[1:])
        except Exception:
            return f"{pool}.{var}"
        return f"parameters.PARAM_{pid}"

    def describe_param(self, pid: ParamId) -> str | None:
        return self.labels.for_param(pid)

    def format_value(
        self, pool: Pool, var: str, value: object, *, lang: str | None = None
    ) -> object:
        """Format value using bound unit definition (enum or symbol)."""
        if not isinstance(var, str):
            return value
        if var.startswith("u"):
            return value

        unit_id: UnitId | None = None
        if var and var[0] in "vnxs":
            try:
                pid = int(var[1:])
            except Exception:
                pid = None
            if pid is not None:
                unit_id = self.param_units.get((pool, pid))

        if unit_id is None:
            return value

        enum_text = self.units.enum_label(unit_id, value)
        if enum_text is not None:
            return enum_text

        sym = self.units.symbol(unit_id)
        return f"{value} {sym}" if sym else value

    def bind_units_from_snapshot(self, snapshot: dict[str, JSON]) -> int:
        """Bind units from snapshot keys like 'P6.u12' -> ('P6', 12) -> unit id in value."""
        if not snapshot:
            return 0
        bound = 0
        for k, v in snapshot.items():
            if "." not in k:
                continue
            pool, var = k.split(".", 1)
            if not var.startswith("u"):
                continue
            try:
                pid = int(var[1:])
            except Exception:
                continue
            uid = str(v) if v is not None else ""
            if not uid:
                continue
            self.touch_param_unit(pool, pid, uid)
            bound += 1
        return bound
