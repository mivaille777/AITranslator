import { useMutation, useQuery } from "@tanstack/react-query"
import { ArrowUpRight, NotebookText } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { createCompanionHandoff } from "../../api/companion"
import { listResearchNotes } from "../../api/quick-actions"
import type { ResearchNoteListItem } from "../../api/types"

export default function ResearchWorkspace() {
  const navigate = useNavigate()
  const notesQuery = useQuery({
    queryKey: ["research-notes", "workspace"],
    queryFn: () => listResearchNotes(20),
    refetchInterval: 5_000,
    retry: 1,
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

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              Research Notes
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">
              Reading evidence saved for later reasoning
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Notes stay in the existing SQLite store. Opening one rebuilds a frozen Companion context and continues in AI Chat.
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
            Total <strong className="ml-1 text-slate-900">{notesQuery.data?.total ?? "—"}</strong>
          </div>
        </div>
      </section>

      {notesQuery.isPending ? (
        <p className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-sm text-slate-400 shadow-sm">
          Loading Research Notes…
        </p>
      ) : notes.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <NotebookText className="mx-auto text-slate-300" size={28} strokeWidth={1.5} />
          <p className="mt-3 text-sm font-medium text-slate-700">No Research Notes yet</p>
          <p className="mt-1 text-xs text-slate-400">Save a browser selection from the Overlay Quick Actions to start a research trail.</p>
        </section>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {notes.map((note) => (
            <article key={note.note_id} className="flex min-h-56 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">{note.display_title}</p>
                {note.section_heading && (
                  <p className="mt-1 truncate text-xs text-slate-400">{note.section_heading}</p>
                )}
              </div>

              <p className="mt-4 line-clamp-5 text-sm leading-6 text-slate-600">{note.excerpt}</p>

              <div className="mt-auto pt-5">
                {note.ai_action && (
                  <span className="mb-3 inline-flex rounded-full bg-cyan-50 px-2.5 py-1 text-[10px] font-medium text-cyan-700">
                    {note.ai_action}
                  </span>
                )}
                <button
                  type="button"
                  disabled={reopenMutation.isPending}
                  className="flex w-full items-center justify-between rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => reopenMutation.mutate(note)}
                >
                  Open in AI Chat
                  <ArrowUpRight size={14} />
                </button>
              </div>
            </article>
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
