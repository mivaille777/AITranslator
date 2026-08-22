export interface ScrollMetrics {
  scrollTop: number
  clientHeight: number
  scrollHeight: number
}

export function overlayChatIsNearTail(
  metrics: ScrollMetrics,
  threshold = 36,
): boolean {
  const remaining = metrics.scrollHeight - metrics.clientHeight - metrics.scrollTop
  return remaining <= Math.max(0, threshold)
}

export function overlayComposerHeight(
  scrollHeight: number,
  minimum = 36,
  maximum = 80,
): number {
  return Math.max(minimum, Math.min(maximum, Math.ceil(scrollHeight)))
}
