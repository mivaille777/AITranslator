import { apiDelete, apiGet, apiPost } from "../../api/client"
import type {
  KnowledgeDocumentDeleteResponse,
  KnowledgeDocumentImportResponse,
  KnowledgeDocumentListResponse,
} from "./knowledge-types"

const KNOWLEDGE_PATH = "/api/knowledge/documents"

export function listKnowledgeDocuments(): Promise<KnowledgeDocumentListResponse> {
  return apiGet(KNOWLEDGE_PATH)
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
