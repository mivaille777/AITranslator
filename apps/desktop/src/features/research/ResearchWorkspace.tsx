import { useMutation, useQuery } from "@tanstack/react-query"
import { ArrowUpRight, MessageSquareText, NotebookText } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { createCompanionHandoff } from "../../api/companion"
import { listResearchNotes } from "../../api/quick-actions"
import type { ResearchNoteListItem } from "../../api/types"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"
import { Card, CardContent, CardHeader } from "../../shared/ui/Card"
import { EmptyState } from "../../shared/ui/EmptyState"

export default function ResearchWorkspace() {
  const navigate = useNavigate()
  const notesQuery = useQuery({
    queryKey: queryKeys.research.notes(20),
    queryFn: () => listResearchNotes(20),
    refetchInterval: queryPolling.researchNotes,
  })

  const reopenMutation = useMutation({
    mutationFn: (note: ResearchNoteListItem) =>
      createCompanionHandoff({
        source_text: note.source_text,
        translated_text: note.translated_text,
        source_language: "auto",
        target_language: "zh-CN",
        resource_url: note.resource_url,
        resource_title: note.resource_title,
        section_heading: note.section_heading,
        context_before: note.context_before,
        context_after: note.context_after,
        source_kind: note.source_kind || "research_note",
        ai_content: note.ai_content,
        ai_action: note.ai_action,
        suggested_prompt: "",
      }),
    onSuccess: () => navigate("/chat"),
  })

  const notes = notesQuery.data?.notes ?? []

  function openNote(note: ResearchNoteListItem) {
    if (note.conversation_id) {
      navigate(`/chat?conversation=${encodeURIComponent(note.conversation_id)}`)
      return
    }
    reopenMutation.mutate(note)
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              Research Notes
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">
              Reading evidence saved for later reasoning
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Notes saved from an active Chat keep their conversation link. Older standalone notes rebuild a frozen Companion context when reopened.
            </p>
          </div>
          <Badge className="self-start sm:self-auto">
            Total · {notesQuery.data?.total ?? "—"}
          </Badge>
        </CardHeader>
      </Card>

      {notesQuery.isPending ? (
        <Card>
          <CardContent className="pt-6 text-sm text-slate-400">
            Loading Research Notes…
          </CardContent>
        </Card>
      ) : notesQuery.isError ? (
        <Card className="border-rose-200">
          <CardContent className="pt-6 text-sm text-rose-700">
            {notesQuery.error instanceof Error
              ? notesQuery.error.message
              : "Unable to load Research Notes."}
          </CardContent>
        </Card>
      ) : notes.length === 0 ? (
        <EmptyState
          icon={<NotebookText size={28} strokeWidth={1.5} />}
          title="No Research Notes yet"
          description="Save a browser selection from the Overlay Quick Actions or save a linked note from AI Chat to start a research trail."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {notes.map((note) => (
            <Card key={note.note_id} className="flex min-h-56 flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">{note.display_title}</p>
                    {note.section_heading && (
                      <p className="mt-1 truncate text-xs text-slate-400">{note.section_heading}</p>
                    )}
                  </div>
                  {note.conversation_id && (
                    <Badge tone="success" className="shrink-0">
                      Linked Chat
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col">
                <p className="line-clamp-5 text-sm leading-6 text-slate-600">{note.excerpt}</p>

                <div className="mt-auto pt-5">
                  {note.ai_action && (
                    <Badge tone="info" className="mb-3">
                      {note.ai_action}
                    </Badge>
                  )}
                  <Button
                    className="w-full justify-between"
                    disabled={reopenMutation.isPending}
                    onClick={() => openNote(note)}
                  >
                    {note.conversation_id ? (
                      <>
                        Continue conversation
                        <MessageSquareText size={14} />
                      </>
                    ) : (
                      <>
                        Open in AI Chat
                        <ArrowUpRight size={14} />
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {reopenMutation.isError && (
        <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {reopenMutation.error instanceof Error ? reopenMutation.error.message : "Unable to reopen Research Note."}
        </p>
      )}
    </div>
  )
}
