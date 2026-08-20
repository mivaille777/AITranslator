const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined

export const API_BASE_URL = (configuredBaseUrl ?? "http://127.0.0.1:8766").replace(/\/$/, "")

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }

  return (await response.json()) as T
}
