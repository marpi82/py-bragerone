poetry run python - <<'PY'
import asyncio, os
from pybragerone.models import ApiModel

EMAIL = os.environ.get("BRAGER_EMAIL")
PASS  = os.environ.get("BRAGER_PASS")

async def main():
    api = ApiModel()
    await api.login(EMAIL, PASS)
    objs = await api.list_objects()
    print("objects:", objs[:2])
    if objs:
        mods = await api.list_modules(objs[0]["id"])
        print("mods:", len(mods))
    await api.ws_close()  # na wypadek
asyncio.run(main())
PY
