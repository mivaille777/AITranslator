from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi.testclient import TestClient

from backend.api.rag_model_dependencies import get_rag_model_manager
from backend.main import create_app
from backend.rag.config import RagEmbeddingConfig, RagRerankerConfig
from backend.rag.embeddings.qwen3 import Qwen3EmbeddingProvider
from backend.rag.exceptions import RagModelManagerError
from backend.rag.model_manager import (
    EMBEDDING_MODEL_ID,
    MODEL_COMPLETION_MANIFEST,
    MODEL_SPECS,
    RERANKER_MODEL_ID,
    ModelManager,
    default_models_root,
)
from backend.rag.models import DocumentChunk, RetrievalCandidate
from backend.rag.rerankers.qwen3 import Qwen3RerankerProvider


class FakeDownloader:
    def __init__(self, *, incomplete: bool = False, error: Exception | None = None):
        self.incomplete = incomplete
        self.error = error
        self.calls: list[dict[str, str]] = []

    def __call__(self, **kwargs: str) -> str:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        target = Path(kwargs["local_dir"])
        spec = next(
            item
            for item in MODEL_SPECS.values()
            if item.repository_id == kwargs["repo_id"]
        )
        for name in spec.required_files:
            (target / name).write_text(f"fixture:{name}", encoding="utf-8")
        if not self.incomplete:
            (target / spec.required_any[0][0]).write_bytes(b"model-weights")
        return str(target)


class CpuTorch:
    class cuda:
        @staticmethod
        def is_available() -> bool:
            return False


class FakeEmbeddingModel:
    def encode(self, texts, **_kwargs):
        return [[1.0, 0.0] for _text in texts]


class FakeRerankerModel:
    def predict(self, pairs, **_kwargs):
        return [1.0 for _pair in pairs]


def test_default_models_root_uses_local_app_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AITRANS_MODELS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_models_root() == tmp_path / "AITrans" / "models"


def test_download_verify_disk_usage_idempotency_and_remove_are_atomic(
    tmp_path: Path,
) -> None:
    downloader = FakeDownloader()
    manager = ModelManager(tmp_path / "models", downloader=downloader)

    assert manager.status(EMBEDDING_MODEL_ID).state == "not_installed"
    installed_path = manager.download(EMBEDDING_MODEL_ID)

    assert installed_path == tmp_path / "models" / "qwen3-embedding-0.6b"
    assert manager.is_installed(EMBEDDING_MODEL_ID) is True
    assert manager.verify(EMBEDDING_MODEL_ID) is True
    assert manager.get_model_path(EMBEDDING_MODEL_ID) == installed_path
    assert manager.disk_usage(EMBEDDING_MODEL_ID) > len(b"model-weights")
    assert manager.status(EMBEDDING_MODEL_ID).state == "installed"
    assert (installed_path / MODEL_COMPLETION_MANIFEST).is_file()
    assert not list((tmp_path / "models").glob("*.partial-*"))

    assert manager.download(EMBEDDING_MODEL_ID) == installed_path
    assert len(downloader.calls) == 1
    assert manager.remove(EMBEDDING_MODEL_ID) is True
    assert manager.remove(EMBEDDING_MODEL_ID) is False
    assert manager.status(EMBEDDING_MODEL_ID).state == "not_installed"


@pytest.mark.parametrize(
    "downloader",
    [
        FakeDownloader(incomplete=True),
        FakeDownloader(error=RuntimeError("network interrupted")),
    ],
)
def test_failed_or_interrupted_download_never_becomes_installed(
    tmp_path: Path,
    downloader: FakeDownloader,
) -> None:
    manager = ModelManager(tmp_path / "models", downloader=downloader)

    with pytest.raises(RagModelManagerError):
        manager.download(RERANKER_MODEL_ID)

    assert manager.is_installed(RERANKER_MODEL_ID) is False
    assert manager.status(RERANKER_MODEL_ID).state == "not_installed"
    assert not (tmp_path / "models" / "qwen3-reranker-0.6b").exists()
    assert not list((tmp_path / "models").glob("*.partial-*"))


def test_invalid_existing_directory_requires_explicit_removal(tmp_path: Path) -> None:
    target = tmp_path / "models" / "qwen3-reranker-0.6b"
    target.mkdir(parents=True)
    (target / "config.json").write_text("{}", encoding="utf-8")
    manager = ModelManager(tmp_path / "models", downloader=FakeDownloader())

    model_status = manager.status(RERANKER_MODEL_ID)
    assert model_status.state == "invalid"
    assert model_status.installed is False
    assert model_status.error.startswith("missing required file")
    with pytest.raises(RagModelManagerError, match="remove it before downloading"):
        manager.download(RERANKER_MODEL_ID)

    assert manager.remove(RERANKER_MODEL_ID) is True


def test_completion_manifest_identity_is_verified(tmp_path: Path) -> None:
    manager = ModelManager(tmp_path / "models", downloader=FakeDownloader())
    target = manager.download(EMBEDDING_MODEL_ID)
    manifest = target / MODEL_COMPLETION_MANIFEST
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["model_id"] = RERANKER_MODEL_ID
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    assert manager.verify(EMBEDDING_MODEL_ID) is False
    assert manager.status(EMBEDDING_MODEL_ID).state == "invalid"
    with pytest.raises(RagModelManagerError, match="manifest model_id mismatch"):
        manager.get_model_path(EMBEDDING_MODEL_ID)


def test_status_reports_downloading_while_snapshot_is_in_progress(
    tmp_path: Path,
) -> None:
    entered = Event()
    release = Event()
    delegate = FakeDownloader()

    def blocking_downloader(**kwargs: str) -> str:
        entered.set()
        assert release.wait(timeout=5)
        return delegate(**kwargs)

    manager = ModelManager(tmp_path / "models", downloader=blocking_downloader)
    errors: list[Exception] = []

    def run_download() -> None:
        try:
            manager.download(EMBEDDING_MODEL_ID)
        except RagModelManagerError as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread = Thread(target=run_download)
    thread.start()
    assert entered.wait(timeout=5)
    assert manager.status(EMBEDDING_MODEL_ID).state == "downloading"
    release.set()
    thread.join(timeout=5)

    assert not errors
    assert not thread.is_alive()
    assert manager.status(EMBEDDING_MODEL_ID).state == "installed"


def test_rag_model_api_lifecycle_and_unknown_model(tmp_path: Path) -> None:
    manager = ModelManager(tmp_path / "models", downloader=FakeDownloader())
    app = create_app()
    app.dependency_overrides[get_rag_model_manager] = lambda: manager
    client = TestClient(app)

    listed = client.get("/api/rag/models")
    assert listed.status_code == 200
    assert len(listed.json()["models"]) == 2
    assert listed.json()["models_root"] == str(manager.models_root)

    downloaded = client.post(f"/api/rag/models/{EMBEDDING_MODEL_ID}/download")
    assert downloaded.status_code == 200
    assert downloaded.json()["changed"] is True
    assert downloaded.json()["model"]["state"] == "installed"
    assert (
        client.post(f"/api/rag/models/{EMBEDDING_MODEL_ID}/verify").json()["verified"]
        is True
    )

    removed = client.delete(f"/api/rag/models/{EMBEDDING_MODEL_ID}")
    assert removed.json()["changed"] is True
    assert removed.json()["model"]["state"] == "not_installed"
    assert client.get("/api/rag/models/unknown").status_code == 404


def test_qwen_providers_resolve_managed_paths_and_force_offline_loading(
    tmp_path: Path,
) -> None:
    manager = ModelManager(tmp_path / "models", downloader=FakeDownloader())
    embedding_path = manager.download(EMBEDDING_MODEL_ID)
    reranker_path = manager.download(RERANKER_MODEL_ID)
    embedding_calls = []
    reranker_calls = []

    def embedding_factory(*args, **kwargs):
        embedding_calls.append((args, kwargs))
        return FakeEmbeddingModel()

    def reranker_factory(*args, **kwargs):
        reranker_calls.append((args, kwargs))
        return FakeRerankerModel()

    embedding = Qwen3EmbeddingProvider(
        RagEmbeddingConfig(dimension=2, device="cpu", warmup=False),
        model_factory=embedding_factory,
        torch_module=CpuTorch(),
        model_manager=manager,
    )
    reranker = Qwen3RerankerProvider(
        RagRerankerConfig(device="cpu"),
        model_factory=reranker_factory,
        torch_module=CpuTorch(),
        model_manager=manager,
    )

    assert embedding.embed_query("query") == [1.0, 0.0]
    reranker.rerank(
        "query",
        [
            RetrievalCandidate(
                chunk=DocumentChunk(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    text="evidence",
                    chunk_index=0,
                ),
                rank=1,
            )
        ],
        top_k=1,
    )
    assert embedding_calls[0][0][0] == str(embedding_path)
    assert embedding_calls[0][1]["local_files_only"] is True
    assert reranker_calls[0][0][0] == str(reranker_path)
    assert reranker_calls[0][1]["local_files_only"] is True
