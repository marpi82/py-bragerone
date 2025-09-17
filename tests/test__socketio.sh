poetry run python - <<'PY'
import asyncio, os
from pybragerone.models import ApiModel

async def main():
    api = ApiModel()
    await api.login(os.environ["BRAGER_EMAIL"], os.environ["BRAGER_PASS"])
    sid = await api.ws_connect()
    print("ws sid:", sid)
    await api.ws_subscribe(["dev1","dev2"])  # podmień na realne id
    await asyncio.sleep(2)
    await api.ws_close()

asyncio.run(main())
PY
