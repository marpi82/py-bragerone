poetry run python - <<'PY'
import asyncio
from pybragerone.models import AssetsModel

async def main():
    m = AssetsModel(lang="pl", debug=True)
    await m.bootstrap_all()
    # gimnastyka na katalogu
    print("labels:", len(m.catalog.labels.items))
    print("units:", len(m.catalog.units.items))
    snap = {"P6.u12": "°C", "P6.v12": 23}
    bound = m.bind_units_from_snapshot(snap)
    print("bound:", bound)
    print("format:", m.format_value("P6", "v12", 23))

asyncio.run(main())
PY
