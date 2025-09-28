ParamStore & LiveAssetCatalog (full drop)
========================================

This archive contains the updated `src/pybragerone` subtree with:
- Pydantic v2-based ParamStore
- LiveAssetCatalog (online assets: i18n, parameter mappings, module.menu)
- Symbol-aware `describe_symbol()`
- Permission-aware `merge_assets_with_permissions()`
- Raw getters for specific assets (parameters/units/module.menu)

Quick start
-----------
.. code-block:: python

    param_store.init_assets(base_url="https://one.brager.pl", session=api.session, lang=None)

    # Known address:
    label, unit, value = await param_store.describe("P4", 1, param_symbol="PARAM_0")

    # Symbolic:
    rec = await param_store.describe_symbol("AKTUALNA_TEMP_CWU_READ")
    # rec => {symbol,pool,idx,chan,label,unit,value}

    merged = await param_store.merge_assets_with_permissions(user_permissions)
    # merged["PARAM_0"] => {pool, idx, chan, label, unit, value}

------
ParamStore.init_assets(...) — inicjalizacja live assetów (i18n, mapy symboli, module.menu) na tej samej sesji aiohttp, co API.
await ParamStore.describe(pool, idx, param_symbol=None) — opis po znanym adresie.
await ParamStore.describe_symbol("...") — NOWOŚĆ: opis po symbolu (np. PARAM_0, AKTUALNA_TEMP_CWU_READ), sam rozwiązuje pool/chan/idx z mapy.
await ParamStore.get_i18n_parameters() / get_i18n_units() — konkretny namespace i18n.
await ParamStore.get_param_mapping(symbol) — mapa dla wybranego symbolu, nie ściąga „wszystkich”.
await ParamStore.get_module_menu() — pełny module.menu.
await ParamStore.merge_assets_with_permissions(perms) — scala module.menu → tylko symbole dopuszczone uprawnieniami, pobiera ich mapy, dokleja etykiety i jednostki z i18n oraz aktualne wartości ze store’a.
