export interface OverlaySourceIdentityInput {
  application?: string
  sourceKind?: string
  resourceUrl?: string
  resourceTitle?: string
  sectionHeading?: string
}

export interface OverlaySourceIdentity {
  applicationLabel: string
  badge: string
  title: string
  detail: string
  tooltip: string
}

const APPLICATION_LABELS: Record<string, string> = {
  "chrome.exe": "Chrome",
  chrome: "Chrome",
  "msedge.exe": "Edge",
  msedge: "Edge",
  "firefox.exe": "Firefox",
  firefox: "Firefox",
  "winword.exe": "Word",
  winword: "Word",
  "acrord32.exe": "Acrobat",
  acrord32: "Acrobat",
  "acrobat.exe": "Acrobat",
  acrobat: "Acrobat",
  "code.exe": "VS Code",
  code: "VS Code",
  "zotero.exe": "Zotero",
  zotero: "Zotero",
  "excel.exe": "Excel",
  excel: "Excel",
  "powerpnt.exe": "PowerPoint",
  powerpnt: "PowerPoint",
}

function normalizedApplication(value = ""): string {
  return value.replaceAll("\\", "/").split("/").pop()?.trim().toLowerCase() ?? ""
}

function fallbackApplicationLabel(value: string, sourceKind: string): string {
  const normalized = normalizedApplication(value)
  if (normalized) {
    const withoutExtension = normalized.replace(/\.exe$/i, "")
    return withoutExtension
      .split(/[-_.\s]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ") || "Application"
  }
  if (sourceKind.includes("browser")) return "Browser"
  if (sourceKind.includes("word")) return "Word"
  if (sourceKind.includes("pdf")) return "PDF"
  return "Desktop"
}

function sourceBadge(sourceKind = ""): string {
  const value = sourceKind.trim().toLowerCase()
  if (value.includes("pdf")) return "PDF"
  if (value.includes("word")) return "WORD"
  if (value.includes("browser")) return "BROWSER"
  if (value.includes("desktop")) return "DESKTOP"
  return value ? value.replaceAll("_", " ").toUpperCase().slice(0, 18) : "SOURCE"
}

function hostname(resourceUrl = ""): string {
  const value = resourceUrl.trim()
  if (!value) return ""
  try {
    return new URL(value).hostname.replace(/^www\./i, "")
  } catch {
    return ""
  }
}

export function resolveOverlaySourceIdentity({
  application = "",
  sourceKind = "",
  resourceUrl = "",
  resourceTitle = "",
  sectionHeading = "",
}: OverlaySourceIdentityInput): OverlaySourceIdentity {
  const applicationKey = normalizedApplication(application)
  const applicationLabel = APPLICATION_LABELS[applicationKey]
    ?? fallbackApplicationLabel(application, sourceKind.toLowerCase())
  const domain = hostname(resourceUrl)
  const title = resourceTitle.trim() || sectionHeading.trim() || domain || "Selected text"
  const detail = domain || sourceKind.replaceAll("_", " ").trim()
  const tooltipParts = [applicationLabel, resourceTitle.trim(), resourceUrl.trim()].filter(Boolean)

  return {
    applicationLabel,
    badge: sourceBadge(sourceKind),
    title,
    detail,
    tooltip: tooltipParts.join(" · "),
  }
}
