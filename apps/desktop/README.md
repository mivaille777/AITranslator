# AITranslator WebReBuild Desktop

This directory contains the React + TypeScript desktop client used by the WebReBuild migration.

## Runtime boundaries

- React owns presentation and interaction.
- FastAPI on `127.0.0.1:8766` owns the WebReBuild business API.
- `127.0.0.1:8765` remains reserved for the existing Browser Selection Bridge.
- `DesktopAdapter` isolates React from Tauri/Electron-specific APIs.
- Normal translation stays deterministic and does not run through LangGraph.

## Development

From `apps/desktop`:

```powershell
npm install
npm run backend:dev
```

In a second terminal:

```powershell
npm run tauri:dev
```

Browser-only frontend development remains available with:

```powershell
npm run dev
```

## Stage 2 translation API

The first migrated business path is:

```text
React
  -> POST /api/translation
  -> FastAPI
  -> TranslationService
  -> existing TranslationManager
  -> TranslationProvider
```

Useful endpoints:

- `GET /health`
- `GET /api/translation/status`
- `POST /api/translation`

The migration intentionally reuses the established translation normalization, cache, and provider implementation under `app/translation/` instead of duplicating those rules in the web client.
