// Single home for magic strings/values used across the frontend, so nothing is
// duplicated between api.js and the components that call it.

export const API_ENDPOINTS = {
  documents: '/documents',
  documentUpload: '/documents/upload',
  ingest: '/ingest',
  query: '/query',
  health: '/health',
}

export const REINGEST_PATH_SUFFIX = '/reingest'

export const KNOWLEDGE_SOURCE_DIR = 'knowledge_source'

// Accepted file types for the single "Add" flow - matches what the backend's
// /documents/upload endpoint accepts (backend/api/routes/documents.py).
export const ACCEPTED_UPLOAD_EXTENSIONS = ['.md', '.pdf']
export const ACCEPTED_UPLOAD_ACCEPT_ATTR = ACCEPTED_UPLOAD_EXTENSIONS.join(',')
