from .client import BragerOneClient
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("py-bragerone")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["BragerOneClient"]
