import { apiDelete, apiGet, apiPost } from "./client"
import type {
  KnowledgeDocument,
  KnowledgeDocumentDeleteResponse,
  KnowledgeDocumentImportResponse,
  KnowledgeDocumentListResponse,
  KnowledgeDocumentOutline,
  KnowledgeDocumentSection,
  KnowledgeDocumentStatusResponse,
  KnowledgeRuntime,
} from "../features/knowledge/knowledge-types"

const KNOWLEDGE_PATH = "/api/knowledge/documents"

export function listKnowledgeDocuments(): Promise<KnowledgeDocumentListResponse> {
  return apiGet(KNOWLEDGE_PATH)
}

export function getKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
  return apiGet(`${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}`)
}

export function getKnowledgeDocumentOutline(documentId: string): Promise<KnowledgeDocumentOutline> {
  return apiGet(`${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}/outline`)
}

export function getKnowledgeDocumentSection(
  documentId: string,
  sectionId: string,
): Promise<KnowledgeDocumentSection> {
  return apiGet(
    `${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}/sections/${encodeURIComponent(sectionId)}`,
  )
}

export function getKnowledgeDocumentStatus(
  documentId: string,
): Promise<KnowledgeDocumentStatusResponse> {
  return apiGet(`${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}/status`)
}

export function addKnowledgeDocument(path: string): Promise<KnowledgeDocumentImportResponse> {
  return apiPost(KNOWLEDGE_PATH, { path })
}

export function deleteKnowledgeDocument(documentId: string): Promise<KnowledgeDocumentDeleteResponse> {
  return apiDelete(`${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}`)
}

export function reindexKnowledgeDocument(documentId: string): Promise<KnowledgeDocumentImportResponse> {
  return apiPost(`${KNOWLEDGE_PATH}/${encodeURIComponent(documentId)}/reindex`, {})
}

export function getKnowledgeRuntime(): Promise<KnowledgeRuntime> {
  return apiGet("/api/knowledge/runtime")
}
