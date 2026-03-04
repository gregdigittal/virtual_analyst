"""
Artifact storage: save/load JSON by tenant, type, and id.
Backend: Supabase Storage (bucket 'artifacts', path tenant_id/artifact_type/id.json).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re as _re
from typing import Any

from shared.fm_shared.errors import StorageError

_log = logging.getLogger(__name__)

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
            try:
                bucket = self._client.storage.from_("artifacts")
                bucket.upload(
                    path, body, file_options={"content-type": "application/json", "upsert": "true"}
                )
            except Exception as exc:
                _log.warning(
                    "artifact_upload_failed, falling back to in-memory: %s (path=%s)",
                    exc,
                    path,
                )
                self._memory[path] = body
        else:
            self._memory[path] = body
        return path

    def load(self, tenant_id: str, artifact_type: str, artifact_id: str) -> dict[str, Any]:
        path = _path(tenant_id, artifact_type, artifact_id)
        if self._client:
            bucket = self._client.storage.from_("artifacts")
            try:
                resp = bucket.download(path)
                return json.loads(resp.decode("utf-8"))
            except Exception as e:
                err_str = str(e).lower()
                # If storage failed, try in-memory fallback (populated when save() failed)
                if path in self._memory:
                    _log.info("artifact_loaded_from_memory_fallback: %s", path)
                    return json.loads(self._memory[path].decode("utf-8"))
                if "404" in str(e) or "not found" in err_str or "object not found" in err_str:
                    raise StorageError(
                        f"Artifact not found: {path}", code="ERR_STOR_NOT_FOUND"
                    ) from e
                raise StorageError(str(e), code="ERR_STOR_OPERATION_FAILED") from e
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

    def delete(self, tenant_id: str, artifact_type: str, artifact_id: str) -> None:
        """Remove an artifact. No-op if not found."""
        path = _path(tenant_id, artifact_type, artifact_id)
        if self._client:
            try:
                self._client.storage.from_("artifacts").remove([path])
            except Exception as exc:
                _log.warning("artifact_delete_failed", extra={"path": path, "error": str(exc)})
        else:
            self._memory.pop(path, None)

    def download_bytes(self, bucket_name: str, path: str) -> bytes:
        """Download raw bytes from a storage bucket (or in-memory fallback).

        Parameters
        ----------
        bucket_name:
            Supabase storage bucket name (e.g. ``"excel-uploads"``).
        path:
            Full path within the bucket.

        Returns
        -------
        bytes
            The raw file content.
        """
        if self._client:
            bucket = self._client.storage.from_(bucket_name)
            return bucket.download(path)
        # In-memory fallback uses "excel:<path>" convention for non-artifact files
        return self._memory.get(f"excel:{path}", b"")

    async def async_save(self, tenant_id: str, artifact_type: str, artifact_id: str, data: dict[str, Any]) -> str:
        return await asyncio.to_thread(self.save, tenant_id, artifact_type, artifact_id, data)

    async def async_load(self, tenant_id: str, artifact_type: str, artifact_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.load, tenant_id, artifact_type, artifact_id)

    async def async_list_ids(self, tenant_id: str, artifact_type: str) -> list[str]:
        return await asyncio.to_thread(self.list_ids, tenant_id, artifact_type)

    async def async_delete(self, tenant_id: str, artifact_type: str, artifact_id: str) -> None:
        await asyncio.to_thread(self.delete, tenant_id, artifact_type, artifact_id)
