import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Search } from "lucide-react"

import {
  deleteConversation,
  getConversations,
  renameConversation,
} from "../../api/conversations"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"
import {
  filterConversationHistory,
  groupConversationHistory,
} from "./conversation-history"

const HISTORY_LIMIT = 50

export default function ConversationHistoryPanel({
  activeConversationId,
  hasCurrentReading,
  onOpen,
  onUseCurrentReading,
  onNewGeneralConversation,
  onDeletedActive,
}: {
  activeConversationId: string
  hasCurrentReading: boolean
  onOpen: (conversationId: string) => void
  onUseCurrentReading: () => void
  onNewGeneralConversation: () => void
  onDeletedActive: () => void
}) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [editingId, setEditingId] = useState("")
  const [editingTitle, setEditingTitle] = useState("")
  const conversationsQuery = useQuery({
    queryKey: queryKeys.conversations.list(HISTORY_LIMIT),
    queryFn: () => getConversations(HISTORY_LIMIT),
    refetchInterval: queryPolling.conversationList,
  })

  const renameMutation = useMutation({
    mutationFn: ({ conversationId, title }: { conversationId: string; title: string }) =>
      renameConversation(conversationId, title),
    onSuccess: () => {
      setEditingId("")
      setEditingTitle("")
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
  const filtered = filterConversationHistory(conversations, search)
  const groups = groupConversationHistory(filtered)

  function beginRename(conversationId: string, title: string) {
    setEditingId(conversationId)
    setEditingTitle(title)
  }

  function commitRename(conversationId: string) {
    const normalized = editingTitle.trim()
    if (!normalized) return
    renameMutation.mutate({ conversationId, title: normalized })
  }

  function remove(conversationId: string, title: string) {
    if (!window.confirm(`Delete “${title}”?`)) return
    deleteMutation.mutate(conversationId)
  }

  return (
    <aside className="border-b border-slate-200 bg-[#060918] p-3 text-slate-200 xl:border-b-0 xl:border-r xl:border-white/[0.06]">
      <div className="px-1 py-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Conversations
            </p>
            <p className="mt-1 text-xs text-slate-400">Local history</p>
          </div>
          <Button size="xs" onClick={onNewGeneralConversation}>
            <Plus size={12} />
            New
          </Button>
        </div>

        {hasCurrentReading && (
          <button
            type="button"
            className="ait-control-motion mt-3 w-full rounded-[13px] border border-cyan-400/20 bg-cyan-400/[0.09] px-3 py-2.5 text-left text-xs font-medium text-cyan-100 hover:bg-cyan-400/[0.14]"
            onClick={onUseCurrentReading}
          >
            Use current reading context
          </button>
        )}

        <label className="mt-3 flex items-center gap-2 rounded-[13px] border border-white/[0.06] bg-white/[0.045] px-3 py-2.5 transition-colors focus-within:border-white/[0.14] focus-within:bg-white/[0.06]">
          <Search size={13} className="shrink-0 text-slate-500" />
          <input
            className="min-w-0 flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600"
            value={search}
            placeholder="Search conversations"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>

      <div className="mt-2 max-h-[540px] overflow-y-auto pr-1">
        {conversationsQuery.isLoading && (
          <p className="px-2 py-3 text-xs text-slate-500">Loading conversations…</p>
        )}
        {!conversationsQuery.isLoading && conversations.length === 0 && (
          <p className="px-2 py-3 text-xs leading-5 text-slate-500">
            No saved conversations yet. Start a General Chat or open the current reading context.
          </p>
        )}
        {!conversationsQuery.isLoading && conversations.length > 0 && filtered.length === 0 && (
          <p className="px-2 py-3 text-xs leading-5 text-slate-500">
            No conversations match “{search.trim()}”.
          </p>
        )}

        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group.label}>
              <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                {group.label}
              </p>
              <div className="space-y-1">
                {group.conversations.map((conversation) => {
                  const active = conversation.conversation_id === activeConversationId
                  const editing = conversation.conversation_id === editingId
                  return (
                    <div
                      key={conversation.conversation_id}
                      className={`ait-conversation-item group rounded-[14px] border p-2.5 ${
                        active
                          ? "translate-x-1 border-white/[0.09] bg-white/[0.09] shadow-[0_8px_24px_rgba(0,0,0,0.12)]"
                          : "border-transparent hover:translate-x-0.5 hover:border-white/[0.06] hover:bg-white/[0.05]"
                      }`}
                    >
                      {editing ? (
                        <div>
                          <input
                            autoFocus
                            className="w-full rounded-[10px] border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
                            value={editingTitle}
                            onChange={(event) => setEditingTitle(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") commitRename(conversation.conversation_id)
                              if (event.key === "Escape") {
                                setEditingId("")
                                setEditingTitle("")
                              }
                            }}
                          />
                          <div className="mt-2 flex gap-1">
                            <button
                              type="button"
                              className="rounded-[9px] bg-slate-800 px-2 py-1 text-[10px] text-slate-200"
                              disabled={renameMutation.isPending}
                              onClick={() => commitRename(conversation.conversation_id)}
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              className="rounded-[9px] px-2 py-1 text-[10px] text-slate-500 hover:text-slate-200"
                              onClick={() => {
                                setEditingId("")
                                setEditingTitle("")
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="block w-full text-left"
                            onClick={() => onOpen(conversation.conversation_id)}
                          >
                            <p className="line-clamp-2 text-xs font-medium leading-5 text-slate-200">
                              {conversation.title}
                            </p>
                            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                              <Badge tone={conversation.context_mode === "reading" ? "info" : "neutral"}>
                                {conversation.context_mode === "reading" ? "Reading" : "General"}
                              </Badge>
                              {conversation.model && <Badge tone="neutral">{conversation.model}</Badge>}
                              {conversation.section_heading && (
                                <span className="line-clamp-1 text-[10px] text-slate-500">
                                  {conversation.section_heading}
                                </span>
                              )}
                            </div>
                          </button>
                          <div className={`mt-2 flex gap-1 transition-opacity ${active ? "opacity-80" : "opacity-0 group-hover:opacity-80"}`}>
                            <button
                              type="button"
                              className="rounded-[8px] px-1.5 py-1 text-[10px] text-slate-500 hover:bg-white/[0.06] hover:text-slate-200"
                              onClick={() => beginRename(conversation.conversation_id, conversation.title)}
                            >
                              Rename
                            </button>
                            <button
                              type="button"
                              className="rounded-[8px] px-1.5 py-1 text-[10px] text-slate-500 hover:bg-rose-500/10 hover:text-rose-300"
                              onClick={() => remove(conversation.conversation_id, conversation.title)}
                            >
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </aside>
  )
}
