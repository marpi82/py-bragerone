# src/bragerone/__init__.py
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("py-bragerone")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .gateway import Gateway

__all__ = ["Gateway", "__version__"]
