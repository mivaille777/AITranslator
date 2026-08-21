import type { ConversationSummary } from "../../api/types"

export interface ConversationHistoryGroup {
  label: "Today" | "Yesterday" | "Previous 7 days" | "Earlier"
  conversations: ConversationSummary[]
}

function startOfLocalDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function normalizedSearchText(conversation: ConversationSummary): string {
  return [
    conversation.title,
    conversation.resource_title,
    conversation.section_heading,
    conversation.model,
    conversation.provider,
  ]
    .join(" ")
    .toLocaleLowerCase()
}

export function filterConversationHistory(
  conversations: ConversationSummary[],
  query: string,
): ConversationSummary[] {
  const normalized = query.trim().toLocaleLowerCase()
  if (!normalized) return conversations
  return conversations.filter((conversation) =>
    normalizedSearchText(conversation).includes(normalized),
  )
}

export function groupConversationHistory(
  conversations: ConversationSummary[],
  now = new Date(),
): ConversationHistoryGroup[] {
  const today = startOfLocalDay(now).getTime()
  const oneDay = 24 * 60 * 60 * 1000
  const groups = new Map<ConversationHistoryGroup["label"], ConversationSummary[]>([
    ["Today", []],
    ["Yesterday", []],
    ["Previous 7 days", []],
    ["Earlier", []],
  ])

  for (const conversation of conversations) {
    const updated = new Date(conversation.updated_at)
    const updatedDay = Number.isNaN(updated.getTime())
      ? 0
      : startOfLocalDay(updated).getTime()
    const ageDays = updatedDay === 0 ? Number.POSITIVE_INFINITY : (today - updatedDay) / oneDay
    const label: ConversationHistoryGroup["label"] =
      ageDays <= 0
        ? "Today"
        : ageDays <= 1
          ? "Yesterday"
          : ageDays <= 7
            ? "Previous 7 days"
            : "Earlier"
    groups.get(label)?.push(conversation)
  }

  return [...groups.entries()]
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, conversations: items }))
}
