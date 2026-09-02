import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BookOpenCheck, Check, CircleAlert, FileSearch, X } from "lucide-react"

import {
  getEvidenceReview,
  synthesizeLiterature,
  updateEvidenceReview,
} from "../../api/evidence-review"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import type { EvidenceReviewStatus } from "./evidence-review-types"

export default function EvidenceReviewPanel({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const queryClient = useQueryClient()
  const workspaceId = workspace.activeResearchWorkspaceId
  const [focus, setFocus] = useState("")

  const reviewQuery = useQuery({
    queryKey: ["research", "evidence-review", workspaceId],
    queryFn: () => getEvidenceReview(workspaceId),
    enabled: Boolean(workspaceId),
  })

  const reviewMutation = useMutation({
    mutationFn: ({ entryId, status }: { entryId: string; status: EvidenceReviewStatus }) =>
      updateEvidenceReview(workspaceId, entryId, status),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: ["research", "evidence-review", workspaceId] })
    },
  })

  const synthesisMutation = useMutation({
    mutationFn: () => synthesizeLiterature(workspaceId, focus.trim()),
  })

  if (!workspaceId) {
    return (
      <section className="ait-surface px-5 py-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-slate-400">Evidence review</p>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          Select a Research Project to review persistent Evidence Ledger claims and build a literature synthesis.
        </p>
      </section>
    )
  }

  const snapshot = reviewQuery.data

  return (
    <section className="ait-surface overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200/70 px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500">
            <BookOpenCheck size={17} />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-slate-400">Stage 20 · Evidence review</p>
            <h2 className="mt-1 text-sm font-semibold text-slate-900">Review machine-grounded claims before synthesis</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Human judgement and machine provenance status stay separate. Accepted claims can still be excluded later if their sources become stale.
            </p>
          </div>
        </div>
        {snapshot ? (
          <div className="flex flex-wrap gap-2 text-[10px] text-slate-500">
            <Badge>{snapshot.accepted_count} accepted</Badge>
            <Badge>{snapshot.needs_review_count} needs review</Badge>
            <Badge>{snapshot.unreviewed_count} unreviewed</Badge>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)]">
        <div className="min-h-0 space-y-3">
          {reviewQuery.isLoading ? <p className="text-xs text-slate-400">Loading Evidence Ledger…</p> : null}
          {reviewQuery.isError ? <p className="text-xs text-rose-600">Unable to load Evidence Review.</p> : null}
          {snapshot?.items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-5 text-xs leading-5 text-slate-500">
              No persistent ledger claims are available yet. Capture a Stage 18 cross-document analysis first.
            </div>
          ) : null}
          {snapshot?.items.map((item) => {
            const entry = item.ledger.entry
            const machine = item.ledger.validation.status
            return (
              <article key={entry.entry_id} className="rounded-xl border border-slate-200/70 bg-white p-4">
                <div className="flex flex-wrap items-center gap-2 text-[10px]">
                  <MachineBadge status={machine} />
                  <span className="rounded-full border border-slate-200 px-2 py-0.5 font-medium text-slate-500">
                    human: {item.review.status.replace("_", " ")}
                  </span>
                  <span className="text-slate-400">{entry.links.length} provenance links</span>
                </div>
                <p className="mt-3 text-xs leading-5 text-slate-700">{entry.statement}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <ReviewButton
                    active={item.review.status === "accepted"}
                    disabled={reviewMutation.isPending}
                    onClick={() => reviewMutation.mutate({ entryId: entry.entry_id, status: "accepted" })}
                  >
                    <Check size={12} /> Accept
                  </ReviewButton>
                  <ReviewButton
                    active={item.review.status === "needs_review"}
                    disabled={reviewMutation.isPending}
                    onClick={() => reviewMutation.mutate({ entryId: entry.entry_id, status: "needs_review" })}
                  >
                    <CircleAlert size={12} /> Needs review
                  </ReviewButton>
                  <ReviewButton
                    active={item.review.status === "rejected"}
                    disabled={reviewMutation.isPending}
                    onClick={() => reviewMutation.mutate({ entryId: entry.entry_id, status: "rejected" })}
                  >
                    <X size={12} /> Reject
                  </ReviewButton>
                </div>
              </article>
            )
          })}
        </div>

        <aside className="rounded-xl border border-slate-200/70 bg-slate-50/55 p-4">
          <div className="flex items-center gap-2 text-slate-600">
            <FileSearch size={14} />
            <p className="text-xs font-semibold">Literature synthesis</p>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-slate-500">
            Only Accepted + currently Supported claims enter consensus. Accepted + Contested claims remain explicit disagreements.
          </p>
          <input
            value={focus}
            onChange={(event) => setFocus(event.target.value)}
            placeholder="Optional synthesis focus"
            maxLength={4000}
            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-slate-400"
          />
          <button
            type="button"
            onClick={() => synthesisMutation.mutate()}
            disabled={synthesisMutation.isPending}
            className="mt-3 w-full rounded-lg bg-slate-900 px-3 py-2 text-[11px] font-semibold text-white transition hover:bg-slate-700 disabled:opacity-40"
          >
            {synthesisMutation.isPending ? "Building synthesis…" : "Build reviewed synthesis"}
          </button>
          {synthesisMutation.data ? (
            <div className="mt-4">
              <div className="mb-2 flex gap-2 text-[10px] text-slate-500">
                <Badge>{synthesisMutation.data.included_count} included</Badge>
                <Badge>{synthesisMutation.data.excluded_count} excluded</Badge>
              </div>
              <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-3 font-sans text-[11px] leading-5 text-slate-600">
                {synthesisMutation.data.draft_markdown}
              </pre>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-slate-200 bg-white px-2 py-1">{children}</span>
}

function MachineBadge({ status }: { status: string }) {
  return <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">machine: {status}</span>
}

function ReviewButton({
  children,
  active,
  disabled,
  onClick,
}: {
  children: React.ReactNode
  active: boolean
  disabled: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[10px] font-semibold transition disabled:opacity-40 ${
        active ? "border-slate-700 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  )
}
