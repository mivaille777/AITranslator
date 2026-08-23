from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from backend.rag.exceptions import RagInvariantError


class IndexStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class IndexManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    content_hash: str = ""
    source_uri: str = ""
    title: str = ""
    parser_version: str = ""
    chunker_version: str = ""
    embedding_model: str = ""
    embedding_dimension: int = Field(default=0, ge=0)
    chunk_ids: list[str] = Field(default_factory=list)
    status: IndexStatus = IndexStatus.PENDING
    indexed_at: datetime | None = None
    error: str = ""


class _ManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    documents: dict[str, IndexManifestRecord] = Field(default_factory=dict)


class IndexManifest:
    """Small, atomically persisted document index manifest."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()
        self._lock = RLock()
        self._data = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self, document_id: str) -> IndexManifestRecord | None:
        with self._lock:
            record = self._data.documents.get(document_id)
            return record.model_copy(deep=True) if record else None

    def find_by_source_uri(self, source_uri: str) -> IndexManifestRecord | None:
        with self._lock:
            for record in self._data.documents.values():
                if record.source_uri == source_uri:
                    return record.model_copy(deep=True)
        return None

    def list_records(self) -> list[IndexManifestRecord]:
        with self._lock:
            return [
                record.model_copy(deep=True)
                for record in sorted(
                    self._data.documents.values(),
                    key=lambda item: item.document_id,
                )
            ]

    def upsert(self, record: IndexManifestRecord) -> None:
        with self._lock:
            self._data.documents[record.document_id] = record.model_copy(deep=True)
            self._save()

    def delete(self, document_id: str) -> bool:
        with self._lock:
            removed = self._data.documents.pop(document_id, None) is not None
            if removed:
                self._save()
            return removed

    def mark_status(
        self,
        document_id: str,
        status: IndexStatus,
        *,
        source_uri: str = "",
        error: str = "",
    ) -> IndexManifestRecord:
        with self._lock:
            existing = self._data.documents.get(document_id)
            record = (
                existing.model_copy(deep=True)
                if existing
                else IndexManifestRecord(
                    document_id=document_id,
                    source_uri=source_uri,
                )
            )
            record.status = status
            record.error = error
            if source_uri:
                record.source_uri = source_uri
            self._data.documents[document_id] = record
            self._save()
            return record.model_copy(deep=True)

    def _load(self) -> _ManifestData:
        if not self._path.exists():
            return _ManifestData()
        try:
            return _ManifestData.model_validate_json(
                self._path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise RagInvariantError(
                f"failed to read RAG index manifest: {self._path}"
            ) from exc

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._data.model_dump_json(indent=2)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, self._path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise RagInvariantError(
                f"failed to persist RAG index manifest: {self._path}"
            ) from exc


def ready_manifest_record(
    *,
    document_id: str,
    content_hash: str,
    source_uri: str,
    title: str,
    parser_version: str,
    chunker_version: str,
    embedding_model: str,
    embedding_dimension: int,
    chunk_ids: list[str],
) -> IndexManifestRecord:
    return IndexManifestRecord(
        document_id=document_id,
        content_hash=content_hash,
        source_uri=source_uri,
        title=title,
        parser_version=parser_version,
        chunker_version=chunker_version,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        chunk_ids=chunk_ids,
        status=IndexStatus.READY,
        indexed_at=datetime.now(UTC),
    )


__all__ = [
    "IndexManifest",
    "IndexManifestRecord",
    "IndexStatus",
    "ready_manifest_record",
]
