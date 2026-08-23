from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.rag.config import RagEmbeddingConfig
from backend.rag.embeddings import EmbeddingProvider, Qwen3EmbeddingProvider
from backend.rag.embeddings.runtime import create_embedding_provider
from backend.rag.exceptions import RagConfigurationError


class MinimalModel:
    def encode(self, texts: list[str], **_kwargs: object) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]


class CpuTorch:
    class cuda:
        @staticmethod
        def is_available() -> bool:
            return False


def test_qwen3_provider_satisfies_embedding_protocol() -> None:
    provider = Qwen3EmbeddingProvider(
        RagEmbeddingConfig(dimension=2, warmup=False),
        model_factory=lambda *_args, **_kwargs: MinimalModel(),
        torch_module=CpuTorch(),
    )

    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension == 2
    assert provider.model_name == "Qwen/Qwen3-Embedding-0.6B"


def test_embedding_device_configuration_is_validated() -> None:
    with pytest.raises(ValidationError, match="device"):
        RagEmbeddingConfig(device="metal")

    assert RagEmbeddingConfig(device=" CUDA ").device == "cuda"


def test_runtime_factory_rejects_unknown_provider() -> None:
    with pytest.raises(RagConfigurationError, match="unsupported"):
        create_embedding_provider(RagEmbeddingConfig(provider="other"))


def test_qwen3_provider_requires_normalized_vectors() -> None:
    with pytest.raises(RagConfigurationError, match="normalize_embeddings"):
        Qwen3EmbeddingProvider(RagEmbeddingConfig(normalize=False))
