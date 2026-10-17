"""Built-in context pack discovery and loader (PRD §9, §16)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

PACKS_DIR = Path(__file__).parent


def get_builtin_packs() -> list[dict[str, Any]]:
    """Discover and return all built-in reference context packs."""
    packs: list[dict[str, Any]] = []
    for p in PACKS_DIR.glob("*_pack.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                packs.append(data)
        except Exception:
            continue
    return packs


def get_builtin_pack(identifier: str) -> Optional[dict[str, Any]]:
    """Retrieve a built-in context pack by pack_id, name, or filename."""
    ident_lower = identifier.lower().strip()
    for pack in get_builtin_packs():
        if (
            pack.get("pack_id", "").lower() == ident_lower
            or pack.get("name", "").lower() == ident_lower
            or pack.get("scope", "").lower() == ident_lower
            or ident_lower in pack.get("pack_id", "").lower()
        ):
            return pack
    return None
