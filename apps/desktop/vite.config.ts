import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { fileURLToPath } from "node:url"

export default defineConfig({
  input: {
    main: fileURLToPath(new URL("./index.html", import.meta.url)),
    overlay: fileURLToPath(new URL("./overlay.html", import.meta.url)),
  },
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    manifest: true,
  },
})
