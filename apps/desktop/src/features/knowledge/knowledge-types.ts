export type KnowledgeDocumentStatus =
  | "pending"
  | "parsing"
  | "chunking"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed"

export interface KnowledgeDocument {
  document_id: string
  title: string
  source_uri: string
  source_type: string
  status: KnowledgeDocumentStatus
  chunk_count: number
  indexed_at: string | null
  error: string
  content_hash: string
  parser_version: string
  chunker_version: string
  embedding_model: string
  embedding_dimension: number
}

export interface KnowledgeDocumentListResponse {
  total: number
  documents: KnowledgeDocument[]
}

export interface KnowledgeDocumentImportResponse {
  document: KnowledgeDocument
  reused_existing: boolean
  elapsed_ms: number
}

export interface KnowledgeDocumentDeleteResponse {
  document_id: string
  deleted: boolean
  source_file_preserved: boolean
}
