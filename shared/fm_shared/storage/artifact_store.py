"""
Artifact storage: save/load JSON by tenant, type, and id.
Backend: Supabase Storage (bucket 'artifacts', path tenant_id/artifact_type/id.json).
"""

from __future__ import annotations

import json
import re as _re
from typing import Any

from shared.fm_shared.errors import StorageError

_SAFE_SEGMENT = _re.compile(r"^[\w\-\.]+$")


def _path(tenant_id: str, artifact_type: str, artifact_id: str) -> str:
    for label, val in [("tenant_id", tenant_id), ("artifact_type", artifact_type), ("artifact_id", artifact_id)]:
        if not val or not _SAFE_SEGMENT.match(val):
            raise StorageError(
                f"Invalid {label}: must be alphanumeric/dash/underscore/dot, got {val!r}",
                code="ERR_STOR_INVALID_PATH",
            )
    return f"{tenant_id}/{artifact_type}/{artifact_id}.json"


class ArtifactStore:
    """Save/load JSON artifacts. Uses Supabase Storage when configured, else in-memory."""

    def __init__(self, supabase_client: Any = None) -> None:
        self._client = supabase_client
        self._memory: dict[str, bytes] = {}

    def save(
        self,
        tenant_id: str,
        artifact_type: str,
        artifact_id: str,
        data: dict[str, Any],
    ) -> str:
        path = _path(tenant_id, artifact_type, artifact_id)
        body = json.dumps(data).encode("utf-8")
        if self._client:
            bucket = self._client.storage.from_("artifacts")
            bucket.upload(
                path, body, file_options={"content-type": "application/json", "upsert": "true"}
            )
        else:
            self._memory[path] = body
        return path

    def load(self, tenant_id: str, artifact_type: str, artifact_id: str) -> dict[str, Any]:
        path = _path(tenant_id, artifact_type, artifact_id)
        if self._client:
            bucket = self._client.storage.from_("artifacts")
            try:
                resp = bucket.download(path)
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower() or "Object not found" in str(e):
                    raise StorageError(
                        f"Artifact not found: {path}", code="ERR_STOR_NOT_FOUND"
                    ) from e
                raise StorageError(str(e), code="ERR_STOR_OPERATION_FAILED") from e
            return json.loads(resp.decode("utf-8"))
        if path not in self._memory:
            raise StorageError(f"Artifact not found: {path}", code="ERR_STOR_NOT_FOUND")
        return json.loads(self._memory[path].decode("utf-8"))

    def list_ids(self, tenant_id: str, artifact_type: str) -> list[str]:
        prefix = f"{tenant_id}/{artifact_type}/"
        if self._client:
            bucket = self._client.storage.from_("artifacts")
            files = bucket.list(prefix=prefix)
            out = []
            for item in files:
                name = item.get("name") or ""
                if name.endswith(".json"):
                    out.append(name.replace(".json", "").split("/")[-1])
            return out
        out = []
        for key in self._memory:
            if key.startswith(prefix) and key.endswith(".json"):
                out.append(key.replace(prefix, "").replace(".json", ""))
        return out
