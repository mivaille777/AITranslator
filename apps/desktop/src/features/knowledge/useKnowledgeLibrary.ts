import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { desktop } from "../../desktop"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import {
  addKnowledgeDocument,
  deleteKnowledgeDocument,
  getKnowledgeRuntime,
  listKnowledgeDocuments,
  reindexKnowledgeDocument,
} from "./knowledge-api"
import { hasActiveKnowledgeDocuments } from "./knowledge-state"

export function useKnowledgeLibrary() {
  const queryClient = useQueryClient()
  const documentsQuery = useQuery({
    queryKey: queryKeys.knowledge.documents,
    queryFn: listKnowledgeDocuments,
    refetchInterval: (query) =>
      hasActiveKnowledgeDocuments(query.state.data?.documents ?? [])
        ? queryPolling.knowledgeActiveDocuments
        : queryPolling.knowledgeDocuments,
  })
  const runtimeQuery = useQuery({
    queryKey: queryKeys.knowledge.runtime,
    queryFn: getKnowledgeRuntime,
    refetchInterval: queryPolling.knowledgeDocuments,
  })

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.documents }),
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.runtime }),
    ])
  }
  const addMutation = useMutation({
    mutationFn: async () => {
      const path = await desktop.files.pickKnowledgeDocument()
      if (!path) return null
      return addKnowledgeDocument(path)
    },
    onSuccess: (result) => {
      if (result) void refresh()
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteKnowledgeDocument,
    onSuccess: () => void refresh(),
  })
  const reindexMutation = useMutation({
    mutationFn: reindexKnowledgeDocument,
    onSuccess: () => void refresh(),
  })

  return {
    documentsQuery,
    runtimeQuery,
    addMutation,
    deleteMutation,
    reindexMutation,
  }
}

export type KnowledgeLibraryController = ReturnType<typeof useKnowledgeLibrary>
