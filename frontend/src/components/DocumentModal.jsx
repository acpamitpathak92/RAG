import { useState } from 'react'

// Edit-only: adding a document happens exclusively through file upload (see
// Sidebar's "Add" button), so this modal only ever edits an existing markdown file.
export default function DocumentModal({ filename, initialContent, onSave, onCancel }) {
  const [content, setContent] = useState(initialContent || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      await onSave({ content })
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="modal">
        <h3>Edit {filename}</h3>
        <textarea
          placeholder="Markdown content..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          autoFocus
        />
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button className="primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
