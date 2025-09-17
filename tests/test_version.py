# mypy: disable-error-code=no-untyped-def
from importlib.metadata import PackageNotFoundError, version

from packaging.version import Version

PKG = "py-bragerone"


def test_version_string_is_parseable():
    try:
        v = version(PKG)
    except PackageNotFoundError:
        # fallback: import bez instalacji — wersja z __init__.py
        import pybragerone as m

        v = getattr(m, "__version__", "0.0.0")
    # parsowalne wg PEP 440 (np. 0.3.0.dev1+gabcdef)
    Version(v)  # nie rzuci wyjątku, jeśli OK
