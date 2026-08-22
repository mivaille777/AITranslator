import "./types"

declare module "./types" {
  interface OverlayStateResponse {
    /**
     * Unified overlay presentation mode. Optional for legacy fixtures, while
     * production responses always provide it through the overlay API.
     */
    mode?: "assistant" | "translation"
    /** Deterministic provider fallback notice shown in translation mode. */
    translation_notice?: string
    /** Persisted companion conversation bound to the current overlay context. */
    companion_conversation_id?: string
  }
}
