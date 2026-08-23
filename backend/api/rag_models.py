from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.rag_model_dependencies import get_rag_model_manager
from backend.models.rag_runtime import (
    RagModelListResponse,
    RagModelOperationResponse,
    RagModelStatusResponse,
)
from backend.rag.exceptions import RagModelManagerError
from backend.rag.model_manager import ModelManager

router = APIRouter(prefix="/api/rag/models", tags=["rag-models"])
ModelManagerDependency = Annotated[ModelManager, Depends(get_rag_model_manager)]


def _raise_model_error(exc: RagModelManagerError) -> None:
    detail = str(exc)
    code = (
        status.HTTP_404_NOT_FOUND
        if detail.startswith("unknown managed RAG model")
        else status.HTTP_409_CONFLICT
    )
    raise HTTPException(status_code=code, detail=detail) from exc


@router.get("", response_model=RagModelListResponse)
def list_rag_models(manager: ModelManagerDependency) -> RagModelListResponse:
    return RagModelListResponse(
        models_root=str(manager.models_root),
        models=manager.statuses(),
    )


@router.get("/{model_id}", response_model=RagModelStatusResponse)
def get_rag_model(
    model_id: str,
    manager: ModelManagerDependency,
) -> RagModelStatusResponse:
    try:
        return manager.status(model_id)
    except RagModelManagerError as exc:
        _raise_model_error(exc)


@router.post(
    "/{model_id}/download",
    response_model=RagModelOperationResponse,
)
def download_rag_model(
    model_id: str,
    manager: ModelManagerDependency,
) -> RagModelOperationResponse:
    try:
        changed = not manager.is_installed(model_id)
        manager.download(model_id)
        return RagModelOperationResponse(
            model=manager.status(model_id), changed=changed
        )
    except RagModelManagerError as exc:
        _raise_model_error(exc)


@router.post(
    "/{model_id}/verify",
    response_model=RagModelStatusResponse,
)
def verify_rag_model(
    model_id: str,
    manager: ModelManagerDependency,
) -> RagModelStatusResponse:
    try:
        manager.verify(model_id)
        return manager.status(model_id)
    except RagModelManagerError as exc:
        _raise_model_error(exc)


@router.delete(
    "/{model_id}",
    response_model=RagModelOperationResponse,
)
def remove_rag_model(
    model_id: str,
    manager: ModelManagerDependency,
) -> RagModelOperationResponse:
    try:
        changed = manager.remove(model_id)
        return RagModelOperationResponse(
            model=manager.status(model_id), changed=changed
        )
    except RagModelManagerError as exc:
        _raise_model_error(exc)


__all__ = ["router"]
