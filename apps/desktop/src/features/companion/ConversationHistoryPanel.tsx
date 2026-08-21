import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  deleteConversation,
  getConversations,
  renameConversation,
} from "../../api/conversations"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"

const HISTORY_LIMIT = 30

export default function ConversationHistoryPanel({
  activeConversationId,
  hasCurrentReading,
  canStartNewConversation,
  onOpen,
  onUseCurrentReading,
  onNewConversation,
  onDeletedActive,
}: {
  activeConversationId: string
  hasCurrentReading: boolean
  canStartNewConversation: boolean
  onOpen: (conversationId: string) => void
  onUseCurrentReading: () => void
  onNewConversation: () => void
  onDeletedActive: () => void
}) {
  const queryClient = useQueryClient()
  const conversationsQuery = useQuery({
    queryKey: queryKeys.conversations.list(HISTORY_LIMIT),
    queryFn: () => getConversations(HISTORY_LIMIT),
    refetchInterval: queryPolling.conversationList,
  })

  const renameMutation = useMutation({
    mutationFn: ({ conversationId, title }: { conversationId: string; title: string }) =>
      renameConversation(conversationId, title),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      if (result.deleted && result.conversation_id === activeConversationId) {
        onDeletedActive()
      }
    },
  })

  const conversations = conversationsQuery.data?.conversations ?? []

  function rename(conversationId: string, currentTitle: string) {
    const next = window.prompt("Rename conversation", currentTitle)?.trim()
    if (!next || next === currentTitle) return
    renameMutation.mutate({ conversationId, title: next })
  }

  function remove(conversationId: string, title: string) {
    if (!window.confirm(`Delete “${title}”?`)) return
    deleteMutation.mutate(conversationId)
  }

  return (
    <aside className="border-b border-slate-200 bg-slate-950 p-3 text-slate-200 xl:border-b-0 xl:border-r xl:border-slate-800">
      <div className="px-1 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Conversations
        </p>
        <p className="mt-1 text-xs text-slate-400">Durable local history</p>
        <div className="mt-3 flex gap-2">
          <Button size="xs" variant="primary" disabled={!canStartNewConversation} onClick={onNewConversation}>
            New
          </Button>
          {hasCurrentReading && (
            <Button size="xs" onClick={onUseCurrentReading}>
              Current
            </Button>
          )}
        </div>
      </div>

      <div className="mt-2 max-h-[560px] space-y-1 overflow-y-auto pr-1">
        {conversationsQuery.isLoading && (
          <p className="px-2 py-3 text-xs text-slate-500">Loading conversations…</p>
        )}
        {!conversationsQuery.isLoading && conversations.length === 0 && (
          <p className="px-2 py-3 text-xs leading-5 text-slate-500">
            No saved conversations yet. The first streamed reply will create one automatically.
          </p>
        )}
        {conversations.map((conversation) => {
          const active = conversation.conversation_id === activeConversationId
          return (
            <div
              key={conversation.conversation_id}
              className={`group rounded-xl border p-2.5 transition ${
                active
                  ? "border-cyan-500/40 bg-cyan-500/10"
                  : "border-transparent hover:border-slate-700 hover:bg-slate-900"
              }`}
            >
              <button
                type="button"
                className="block w-full text-left"
                onClick={() => onOpen(conversation.conversation_id)}
              >
                <p className="line-clamp-2 text-xs font-medium leading-5 text-slate-200">
                  {conversation.title}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {conversation.model && <Badge tone="neutral">{conversation.model}</Badge>}
                  {conversation.section_heading && (
                    <span className="line-clamp-1 text-[10px] text-slate-500">
                      {conversation.section_heading}
                    </span>
                  )}
                </div>
              </button>
              <div className="mt-2 flex gap-1 opacity-70 transition group-hover:opacity-100">
                <button
                  type="button"
                  className="rounded px-1.5 py-1 text-[10px] text-slate-500 hover:bg-slate-800 hover:text-slate-200"
                  onClick={() => rename(conversation.conversation_id, conversation.title)}
                >
                  Rename
                </button>
                <button
                  type="button"
                  className="rounded px-1.5 py-1 text-[10px] text-slate-500 hover:bg-rose-500/10 hover:text-rose-300"
                  onClick={() => remove(conversation.conversation_id, conversation.title)}
                >
                  Delete
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
