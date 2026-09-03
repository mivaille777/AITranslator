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
  structure_quality?: string
  section_count?: number
  reindex_recommended?: boolean
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

export interface KnowledgeDocumentStatusResponse {
  document_id: string
  status: KnowledgeDocumentStatus
  chunk_count: number
  indexed_at: string | null
  error: string
}

export interface KnowledgeDocumentOutlineSection {
  section_id: string
  heading: string
  level: number
  parent_section_id: string | null
  section_path: string[]
  page_start: number | null
  page_end: number | null
  block_count: number
  has_equations: boolean
  has_tables: boolean
  has_figures: boolean
  reference_section: boolean
  synthetic: boolean
}

export interface KnowledgeDocumentOutline {
  document_id: string
  title: string
  page_count: number
  section_count: number
  sections: KnowledgeDocumentOutlineSection[]
}

export interface KnowledgeDocumentSection {
  document_id: string
  section_id: string
  heading: string
  level: number
  section_path: string[]
  page_start: number | null
  page_end: number | null
  text: string
  truncated: boolean
}

export interface KnowledgeRuntime {
  enabled: boolean
  embedding_provider: string
  embedding_model: string
  embedding_status: string
  device: string
  dimension: number
  vector_store_provider: string
  collection_name: string
  document_count: number
  ready_document_count: number
  indexed_chunk_count: number
  max_file_bytes: number
}
