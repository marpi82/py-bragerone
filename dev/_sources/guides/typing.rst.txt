Typing guidelines for py-bragerone
==================================

This document summarizes how to annotate and use types in this project.
Follow these rules consistently to keep the codebase mypy-clean and forward-compatible with Python ≥ 3.13 and 3.14-dev.

General rules
-------------
- Always add type hints (functions, methods, variables, constants).
- Use built-in generics (PEP 585): ``list[int]``, ``dict[str, Any]``, ``tuple[str, int]``.
