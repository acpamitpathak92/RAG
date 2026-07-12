// Thin wrapper around the backend's REST API. Every call is a relative path
// (e.g. "/documents") so it works both through the Vite dev proxy and, in a
// production build, when served from the same origin as the API.

import { API_ENDPOINTS, KNOWLEDGE_SOURCE_DIR, REINGEST_PATH_SUFFIX } from './constants'

async function request(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ''}`)
  }
  return res.json()
}

export function listDocuments() {
  return request(API_ENDPOINTS.documents)
}

export function getDocument(docId) {
  return request(`${API_ENDPOINTS.documents}/${docId}`)
}

export function updateDocument(docId, content) {
  return request(`${API_ENDPOINTS.documents}/${docId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function deleteDocument(docId) {
  return request(`${API_ENDPOINTS.documents}/${docId}`, { method: 'DELETE' })
}

// Re-runs ingestion against whatever is currently on disk for this doc (no upload needed) -
// useful for PDFs, which can't be edited in-browser, or any file edited outside the app.
export function reingestDocument(docId) {
  return request(`${API_ENDPOINTS.documents}/${docId}${REINGEST_PATH_SUFFIX}`, { method: 'POST' })
}

// The single way to add a document: upload a real .md or .pdf file. The backend
// decides how to parse/ingest it based on the extension.
export function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request(API_ENDPOINTS.documentUpload, { method: 'POST', body: formData })
}

// Ingests every file already sitting in a folder (default: knowledge_source/).
// Markdown and PDF are separate source types on the backend, so this fires both
// and merges the summaries - a single "Ingest All" click covers a mixed folder.
export async function ingestAll(corpusDir = KNOWLEDGE_SOURCE_DIR) {
  const [markdown, pdf] = await Promise.all([
    request(API_ENDPOINTS.ingest, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corpus_dir: corpusDir, source_type: 'markdown' }),
    }),
    request(API_ENDPOINTS.ingest, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corpus_dir: corpusDir, source_type: 'pdf' }),
    }),
  ])
  return {
    ingested: markdown.ingested + pdf.ingested,
    skipped_unchanged: markdown.skipped_unchanged + pdf.skipped_unchanged,
    versions_bumped: markdown.versions_bumped + pdf.versions_bumped,
  }
}

export function askQuestion(query) {
  return request(API_ENDPOINTS.query, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
}
