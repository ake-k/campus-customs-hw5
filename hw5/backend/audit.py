"""Append-only audit trail at output/audit_trail.json.

The file is one JSON array of AuditEvent objects. Every run appends to it;
nothing ever truncates or rewrites earlier events. Writes go to a temp file
that is then swapped in, so a crash can't leave half-written JSON behind.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AUDIT_TEXT_LIMIT, AUDIT_TRAIL
from models import AuditEvent

_lock = threading.Lock()


def clip(value: Any, limit: int = AUDIT_TEXT_LIMIT) -> Any:
    """Keep audit entries readable: long strings are cut, nested values are clipped too."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: clip(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clip(v, limit) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return clip(str(value), limit)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append(event: AuditEvent, path: Path = AUDIT_TRAIL) -> None:
    with _lock:
        events: list = []
        if path.exists() and path.stat().st_size:
            try:
                events = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Never lose earlier history: keep the unreadable file and start a fresh one.
                path.rename(path.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json"))
        events.append(event.model_dump())
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
