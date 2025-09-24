from __future__ import annotations
import json
import re
from typing import Any

def _strip_trailing_commas(s: str) -> str:
    # remove trailing commas before } or ]
    return re.sub(r",\s*(?=[}\]])", "", s)

def extract_embedded_json(js_text: str) -> Any:
    """Extract JSON object embedded in a compiled JS module.

    Supports patterns seen in one.brager.pl bundles:
    - export default JSON.parse("...")
    - export default { ... }
    - var X = {...}; export default X
    """
    m = re.search(r"export\s+default\s+JSON\.parse\((\".*?\")\)", js_text, re.DOTALL)
    if m:
        unescaped = json.loads(m.group(1))
        return json.loads(unescaped)
    m = re.search(r"export\s+default\s+(\{.*\})\s*;?\s*$", js_text, re.DOTALL)
    if m:
        return json.loads(_strip_trailing_commas(m.group(1)))
    m = re.search(r"var\s+\w+\s*=\s*(\{.*\})\s*;\s*export\s+default\s+\w+", js_text, re.DOTALL)
    if m:
        return json.loads(_strip_trailing_commas(m.group(1)))
    raise ValueError("No recognizable embedded JSON found in JS module.")
