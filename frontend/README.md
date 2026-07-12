# Issue RAG — React UI

A small, clean React app for the RAG system: a two-pane layout with a knowledge-base
sidebar (list, add, edit, delete, bulk ingest, PDF upload) and a chat panel for
asking questions with collapsible citations and a confidence badge.

## Run

Requires the backend running first (see the main [README](../README.md)):

```
uvicorn backend.api.main:app --port 8000
```

Then, in this folder:

```
npm install
npm run dev
```

Open **http://localhost:5173/**. The dev server proxies `/query`, `/documents`,
`/ingest`, and `/health` to `http://127.0.0.1:8000` (configured in `vite.config.js`) -
no CORS setup or hardcoded backend URL needed. Override the backend location with
the `RAG_API_PROXY_TARGET` env var if it's not on the default host/port.

## Structure

```
src/
├── api.js               # fetch wrappers for every backend endpoint
├── App.jsx               # top-level layout: header + Sidebar + ChatPanel
├── App.css                # all app styling (plain CSS, no UI library)
└── components/
    ├── Sidebar.jsx         # document list, add/edit/delete, "Ingest All", PDF upload
    ├── DocumentModal.jsx   # add/edit form used by Sidebar
    └── ChatPanel.jsx        # message history, composer, citation rendering
```

## Notable behavior

- **Ingest All** fires both a markdown and a PDF ingest pass against `knowledge_source/`
  and merges the summaries, so a single click covers a mixed folder.
- **Upload PDF** posts a real file via `multipart/form-data` to `POST /documents/upload`
  and ingests it immediately - no need to drop it in the folder and click Ingest All.
- Editing is only offered for markdown documents; PDFs are binary and can't be edited
  as text (the backend returns a 400 if you try) - delete and re-upload instead.
- Enter sends a chat message; Shift+Enter inserts a newline. Citations are collapsed
  behind a "Citations (n)" toggle by default.

## Build for production

```
npm run build
```

Outputs to `dist/`. Nothing currently serves this automatically - the FastAPI app
serves the simpler static `ui/` folder at `/` by default (see `backend/api/main.py`).
Point a static file server (or swap the `StaticFiles` mount) at `frontend/dist/` if
you want the React build served instead.
