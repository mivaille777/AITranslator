from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from backend.rag.config import RagConfig
from backend.rag.embeddings import EmbeddingProvider
from backend.rag.index_manifest import IndexManifest, IndexManifestRecord
from backend.rag.index_service import IndexDocumentResult, IndexService

DEFAULT_KNOWLEDGE_MAX_FILE_BYTES = 100 * 1024 * 1024
SUPPORTED_KNOWLEDGE_SUFFIXES = frozenset(
    {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}
)


@dataclass(frozen=True, slots=True)
class KnowledgeRuntimeSnapshot:
    enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_status: str
    device: str
    dimension: int
    vector_store_provider: str
    collection_name: str
    document_count: int
    ready_document_count: int
    indexed_chunk_count: int
    max_file_bytes: int
    allowed_roots: tuple[str, ...]


class KnowledgeLibraryService:
    """Safe local-file boundary over indexing and manifest operations."""

    def __init__(
        self,
        *,
        index_service: IndexService,
        manifest: IndexManifest,
        config: RagConfig,
        embedding_provider: EmbeddingProvider,
        allowed_roots: tuple[str | Path, ...] | None = None,
        max_file_bytes: int = DEFAULT_KNOWLEDGE_MAX_FILE_BYTES,
    ) -> None:
        self._index_service = index_service
        self._manifest = manifest
        self._config = config
        self._embedding_provider = embedding_provider
        roots = allowed_roots or (Path.home(),)
        self._allowed_roots = tuple(Path(root).expanduser().resolve() for root in roots)
        self._max_file_bytes = max(1, int(max_file_bytes))

    def validate_source_path(self, source_path: str | Path) -> Path:
        raw = str(source_path or "").strip()
        if not raw:
            raise ValueError("document path must not be empty")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise ValueError("document path must be absolute")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("document path must reference a file")
        if not any(resolved.is_relative_to(root) for root in self._allowed_roots):
            raise PermissionError("document path is outside allowed knowledge roots")
        if resolved.suffix.lower() not in SUPPORTED_KNOWLEDGE_SUFFIXES:
            raise ValueError(
                f"unsupported document type: {resolved.suffix.lower() or '<none>'}"
            )
        if resolved.stat().st_size > self._max_file_bytes:
            raise ValueError(
                f"document exceeds the maximum size of {self._max_file_bytes} bytes"
            )
        return resolved

    def import_document(self, source_path: str | Path) -> IndexDocumentResult:
        return self._index_service.index_document(
            self.validate_source_path(source_path)
        )

    def list_documents(self) -> list[IndexManifestRecord]:
        return self._manifest.list_records()

    def get_document(self, document_id: str) -> IndexManifestRecord | None:
        return self._manifest.get(str(document_id or "").strip())

    def reindex_document(self, document_id: str) -> IndexDocumentResult | None:
        record = self.get_document(document_id)
        if record is None:
            return None
        path = self.validate_source_path(self._path_from_file_uri(record.source_uri))
        return self._index_service.reindex_document(path)

    def delete_document(self, document_id: str) -> bool:
        return self._index_service.delete_document(str(document_id or "").strip())

    def runtime(self) -> KnowledgeRuntimeSnapshot:
        records = self.list_documents()
        embedding_runtime = getattr(self._embedding_provider, "runtime", None)
        status = getattr(embedding_runtime, "status", "uninitialized")
        status_value = getattr(status, "value", status)
        device = str(
            getattr(embedding_runtime, "device", self._config.embedding.device)
            or self._config.embedding.device
        )
        return KnowledgeRuntimeSnapshot(
            enabled=self._config.enabled,
            embedding_provider=self._config.embedding.provider,
            embedding_model=self._embedding_provider.model_name,
            embedding_status=str(status_value or "uninitialized"),
            device=device,
            dimension=self._embedding_provider.dimension,
            vector_store_provider=self._config.vector_store.provider,
            collection_name=self._config.vector_store.collection_name,
            document_count=len(records),
            ready_document_count=sum(
                record.status.value == "ready" for record in records
            ),
            indexed_chunk_count=sum(len(record.chunk_ids) for record in records),
            max_file_bytes=self._max_file_bytes,
            allowed_roots=tuple(str(root) for root in self._allowed_roots),
        )

    @staticmethod
    def _path_from_file_uri(source_uri: str) -> Path:
        parsed = urlparse(source_uri)
        if parsed.scheme != "file":
            raise ValueError("indexed document source is not a local file URI")
        path = url2pathname(unquote(parsed.path))
        if os.name == "nt" and len(path) >= 3 and path[0] in "/\\" and path[2] == ":":
            path = path[1:]
        if parsed.netloc:
            path = f"//{parsed.netloc}{path}"
        return Path(path)


__all__ = [
    "DEFAULT_KNOWLEDGE_MAX_FILE_BYTES",
    "SUPPORTED_KNOWLEDGE_SUFFIXES",
    "KnowledgeLibraryService",
    "KnowledgeRuntimeSnapshot",
]
