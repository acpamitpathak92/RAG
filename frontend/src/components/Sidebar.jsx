import { useEffect, useRef, useState } from 'react'
import {
  deleteDocument,
  getDocument,
  ingestAll,
  listDocuments,
  reingestDocument,
  updateDocument,
  uploadDocument,
} from '../api'
import { ACCEPTED_UPLOAD_ACCEPT_ATTR } from '../constants'
import DocumentModal from './DocumentModal'
import { PencilIcon, RefreshIcon, TrashIcon } from './Icons'

function basename(path) {
  if (!path) return ''
  return path.split(/[\\/]/).pop()
}

export default function Sidebar() {
  const [documents, setDocuments] = useState([])
  const [loadError, setLoadError] = useState('')
  const [ingestStatus, setIngestStatus] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [reingestingId, setReingestingId] = useState(null)
  const [editTarget, setEditTarget] = useState(null) // null | { docId, filename, content }
  const fileInputRef = useRef(null)

  async function refresh() {
    try {
      const docs = await listDocuments()
      setDocuments(docs)
      setLoadError('')
    } catch (err) {
      setLoadError(err.message)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleIngestAll() {
    setIngesting(true)
    setIngestStatus('Ingesting knowledge_source/ ...')
    try {
      const summary = await ingestAll()
      setIngestStatus(
        `Ingested: ${summary.ingested}, skipped (unchanged): ${summary.skipped_unchanged}, versions bumped: ${summary.versions_bumped}`
      )
      await refresh()
    } catch (err) {
      setIngestStatus(`Error: ${err.message}`)
    } finally {
      setIngesting(false)
    }
  }

  async function openEdit(docId) {
    try {
      const data = await getDocument(docId)
      setEditTarget({ docId, filename: data.filename, content: data.content })
    } catch (err) {
      alert(`Error loading document: ${err.message}`)
    }
  }

  async function handleDelete(docId) {
    if (!confirm('Delete this document? This removes it from the knowledge base and disk.')) return
    try {
      await deleteDocument(docId)
      await refresh()
    } catch (err) {
      alert(`Error deleting document: ${err.message}`)
    }
  }

  async function handleReingest(docId) {
    setReingestingId(docId)
    try {
      const result = await reingestDocument(docId)
      setIngestStatus(`Reingested: ${result.status}`)
      await refresh()
    } catch (err) {
      alert(`Error reingesting document: ${err.message}`)
    } finally {
      setReingestingId(null)
    }
  }

  async function handleEditSave({ content }) {
    await updateDocument(editTarget.docId, content)
    setEditTarget(null)
    await refresh()
  }

  async function handleFileSelected(e) {
    const file = e.target.files?.[0]
    e.target.value = '' // reset so the same file can be re-selected later
    if (!file) return

    setUploading(true)
    setIngestStatus(`Uploading ${file.name}...`)
    try {
      const result = await uploadDocument(file)
      setIngestStatus(`Uploaded ${result.filename} (${result.status})`)
      await refresh()
    } catch (err) {
      setIngestStatus(`Error uploading file: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <aside id="sidebar">
      <div className="sidebar-header">
        <h2>Knowledge Base</h2>
        <div className="sidebar-header-actions">
          <button onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? 'Adding...' : 'Add'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_UPLOAD_ACCEPT_ATTR}
            hidden
            onChange={handleFileSelected}
          />
        </div>
      </div>

      <div className="ingest-bar">
        <button onClick={handleIngestAll} disabled={ingesting}>
          {ingesting ? 'Ingesting...' : 'Ingest All'}
        </button>
        {ingestStatus && <div className="ingest-status">{ingestStatus}</div>}
      </div>

      <div id="docList">
        {loadError && <div className="doc-empty">Error loading documents: {loadError}</div>}
        {!loadError && documents.length === 0 && (
          <div className="doc-empty">No documents yet. Click "Ingest All" or "Add".</div>
        )}
        {documents.map((doc) => (
          <div className="doc-card" key={doc.doc_id}>
            <div className="doc-row">
              <span className="doc-filename" title={doc.file_path || doc.doc_id}>
                {basename(doc.file_path) || doc.title || doc.doc_id}
              </span>
              <div className="doc-icon-actions">
                {doc.source !== 'pdf' && (
                  <button title="Edit" aria-label="Edit" onClick={() => openEdit(doc.doc_id)}>
                    <PencilIcon />
                  </button>
                )}
                <button
                  title="Reingest"
                  aria-label="Reingest"
                  disabled={reingestingId === doc.doc_id}
                  onClick={() => handleReingest(doc.doc_id)}
                >
                  <RefreshIcon className={reingestingId === doc.doc_id ? 'spinning' : ''} />
                </button>
                <button title="Delete" aria-label="Delete" onClick={() => handleDelete(doc.doc_id)}>
                  <TrashIcon />
                </button>
              </div>
            </div>
            <div className="doc-meta">
              {doc.chunk_count} chunk{doc.chunk_count === 1 ? '' : 's'} · v{doc.version} · {doc.source || 'unknown'}
            </div>
          </div>
        ))}
      </div>

      {editTarget && (
        <DocumentModal
          filename={editTarget.filename}
          initialContent={editTarget.content}
          onSave={handleEditSave}
          onCancel={() => setEditTarget(null)}
        />
      )}
    </aside>
  )
}
