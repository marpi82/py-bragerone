Param Store Metadata Reference
==============================

This document describes the structure of the dictionary returned by
``ParamResolver.describe_symbol()``. The same schema is used by diagnostics
(e.g. ``scripts/tests/test_param_store_flow.py``) and by Home Assistant
adapters when interpreting dynamic metadata from the BragerOne assets.

The reference below follows Python typing notation and highlights how each
field should be interpreted.

Top-level keys
--------------

``symbol`` (``str``)
    The original routing token such as ``"PARAM_66"`` or
    ``"URUCHOMIENIE_KOTLA"``.

``pool`` (``str | None``)
    Pool identifier extracted from the asset map (for example ``"P6"``).
    Absent when the asset does not expose a canonical pool.

``idx`` (``int | None``)
    Channel index within the pool. ``None`` when no concrete address could
    be resolved.

``chan`` (``str | None``)
    Preferred channel letter (``"v"``, ``"s"``, ``"u"`` …) inferred from the
    mapping. ``None`` when detection failed.

``label`` (``str | None``)
    Localised label resolved from the ``parameters`` i18n namespace.

``unit`` (``str | dict[str, str] | None``)
    Human-readable unit or enumeration mapping. The formatter first inspects
    the live value (``ParamFamilyModel.unit_code``) and falls back to the
    asset metadata. Enumeration dictionaries always map stringified codes to
    translated labels.

``value`` (``Any``)
    Latest stored value from REST prime or WebSocket updates. May be ``None``
    when the device has not yet provided a reading.

``unit_code`` (``Any``)
    Raw unit channel value cached in ``ParamFamilyModel``. Useful for
    lower-level integrations that need the code before translation.

``min`` / ``max`` (``Any``)
    Cached min/max raw channels when present. Integrators should treat these
    as advisory limits, not strict validation rules.

``status`` (``Any``)
    Raw status channel payload, typically a bitfield integer. Combine with
    ``mapping.status_conditions`` or ``mapping.status_flags`` for semantics.

``mapping_origin`` (``str | None``)
    Origin string recorded by the catalog (``"asset:<url>"`` or
    ``"inline:index"``). Handy for debugging asset regressions.

``mapping`` (``dict[str, Any] | None``)
    Structured metadata extracted from the asset catalog. When ``None`` the
    catalog did not yield a mapping (rare).

Mapping dictionary
------------------

``component_type`` (``str | None``)
    Sanitised component identifier (for example ``"SWITCH"``). Prefixes such
    as ``"u."`` or ``"t."`` are stripped for readability.

``channels`` (``dict[str, list[ChannelDescriptor]]``)
    Cleaned channel descriptors grouped by logical purpose. Keys include
    ``"value"``, ``"command"``, ``"unit"``, ``"status"``, ``"min"`` and
    ``"max"``. Each descriptor in the list has the shape described below.

``paths`` (``dict[str, list[dict[str, Any]]]``)
    Raw paths exactly as returned by the catalog. These retain all original
    keys and are mainly useful when debugging parser edge cases.

``status_conditions`` (``dict[str, list[ChannelDescriptor]]``)
    Human-readable mapping of status condition names to the channels/bits that
    drive them. Condition names are unprefixed (``"INVISIBLE"`` instead of
    ``"[t.INVISIBLE]"``). ``ChannelDescriptor`` entries reuse the same schema
    as ``channels`` but always include the ``bit`` that triggers the condition.

``limits`` (``dict[str, Any] | None``)
    Optional limit metadata present in some assets (for example structured
    ranges or validation rules). Contents are asset-defined; treat as a free
    form dictionary.

``status_flags`` (``list[Any]``)
    Sanitised list of auxiliary status definitions. String entries are cleaned
    from helper prefixes, dictionaries retain unknown keys but have their
    ``name`` field normalised.

``command_rules`` (``list[CommandRule]``)
    Normalised automation logic extracted from ``any``/``all``/``when`` blocks
    inside the asset. Each rule describes a command that the UI may issue when
    specific conditions are met. The ``CommandRule`` schema is described below.

``units_source`` (``str | int | float | None``)
    Raw unit code stored in the asset map prior to localisation. When the value
    is a string it is also cleaned from helper prefixes.

``origin`` (``str``)
    Same as ``mapping_origin`` for convenience.

``raw`` (``dict[str, Any]``)
    Untouched asset payload. Kept for debugging and future i18n enrichment.

ChannelDescriptor schema
------------------------

``channel`` (``str``)
    Fully qualified address (``"P6.v66"``). This is the preferred key for
    downstream logic.

``address`` (``str``)
    Duplicate of ``channel`` kept for backwards compatibility.

``bit`` (``int | None``)
    Bit index for boolean/status channels. Absent for value/unit paths.

``condition`` (``str | None``)
    Condition name the entry belongs to (only present when the entry is linked
    with ``status_conditions``).

CommandRule schema
------------------

``logic`` (``str``)
    Source branch within the asset (``"any"``, ``"all"`` or ``"when"``).

``kind`` (``str``)
    Branch type (``"if"``, ``"elseif"`` or ``"else"``) mirroring the original
    control flow.

``command`` (``str``)
    Normalised command identifier without the ``"o."`` prefix.

``value`` (``Any``)
    Optional value sent with the command. Logical constants (``true``/``false``)
    are already converted to Python ``bool``.

``conditions`` (``list[ConditionDescriptor]``)
    Evaluated guards for the rule. Empty when the branch was an unconditional
    ``else``.

ConditionDescriptor schema
--------------------------

``operation`` (``str | None``)
    Sanitised operator name (for example ``"equalTo"`` or ``"notEqualTo"``).

``expected`` (``Any``)
    Value used by the comparison. ``void 0`` and ``undefined`` become ``None``;
    logical negations (``!0``/``!1``) map to booleans.

``targets`` (``list[ChannelDescriptor]]``)
    Target addresses checked by the condition. Each entry mirrors the
    ``ChannelDescriptor`` schema (sans ``condition``) and is ready to be mapped
    onto live ParamStore values.

Usage guidelines
----------------

* Prefer ``channel`` over ``address`` when consuming path entries – it already
  contains the cleaned ``P?.c?`` notation.
* Combine ``status`` with ``status_conditions`` to derive entity states. Each
  condition describes the bit required to mark the state as active.
* To simulate UI actions (for example resetting the fuel level), locate the
  relevant entry under ``command_rules`` and apply the listed condition checks
  before issuing the matching ``command`` with its ``value``.
* Preserve ``raw`` when caching data for offline analysis – upstream asset
  changes can be re-parsed without fetching everything again.
