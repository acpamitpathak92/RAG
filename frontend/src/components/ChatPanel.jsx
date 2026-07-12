import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useMemo, useRef, useState } from 'react'
import { askQuestion } from '../api'
import { CheckIcon, CopyIcon } from './Icons'

marked.setOptions({ breaks: true }) // treat single line breaks in the answer as <br>, not just double-newline paragraphs

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''))
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard API unavailable (e.g. insecure context) - fail silently, nothing to recover
    }
  }

  return (
    <button className="copy-btn" onClick={handleCopy} title="Copy response">
      {copied ? <CheckIcon /> : <CopyIcon />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function CorrectionNotice({ originalQuery, correctedQuery }) {
  return (
    <div className="correction-notice">
      Understood as: <strong>{correctedQuery}</strong>
      <span className="correction-original"> (you typed: "{originalQuery}")</span>
    </div>
  )
}

function CitationCard({ citation }) {
  return (
    <div className="citation-card">
      <div className="citation-title">
        [{citation.marker}] {citation.doc_title || citation.doc_id}
      </div>
      {citation.chunk_text && <div className="citation-snippet">"{citation.chunk_text}"</div>}
      <div className="citation-ids">
        doc={citation.doc_id} · chunk={citation.chunk_id} · source={citation.source}
      </div>
    </div>
  )
}

function AssistantMessage({
  answer,
  citations,
  confidenceScore,
  needsCaveat,
  error,
  originalQuery,
  correctedQuery,
  queryWasCorrected,
}) {
  const html = useMemo(() => renderMarkdown(answer), [answer])

  if (error) {
    return (
      <div className="msg assistant">
        <div className="bubble bubble-plain">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="msg assistant">
      {queryWasCorrected && (
        <CorrectionNotice originalQuery={originalQuery} correctedQuery={correctedQuery} />
      )}
      <div className="bubble">
        <div className="bubble-toolbar">
          <CopyButton text={answer} />
        </div>
        <div className="markdown-content" dangerouslySetInnerHTML={{ __html: html }} />
      </div>
      <div className="meta-row">
        <span className={`badge ${needsCaveat ? 'warn' : 'ok'}`}>
          {needsCaveat ? 'low confidence: ' : 'confidence: '}
          {confidenceScore.toFixed(2)}
        </span>
        <details className="citations">
          <summary>Citations ({citations.length})</summary>
          {citations.length === 0 ? (
            <div className="citation-card">(no citations)</div>
          ) : (
            citations.map((c) => <CitationCard key={c.marker} citation={c} />)
          )}
        </details>
      </div>
    </div>
  )
}

export default function ChatPanel() {
  const [messages, setMessages] = useState([]) // { role: 'user'|'assistant', ...payload }
  const [input, setInput] = useState('')
  const [status, setStatus] = useState('')
  const [sending, setSending] = useState(false)
  const messagesRef = useRef(null)

  function scrollToBottom() {
    requestAnimationFrame(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    })
  }

  async function sendQuery() {
    const query = input.trim()
    if (!query || sending) return

    setMessages((prev) => [...prev, { role: 'user', text: query }])
    setInput('')
    setSending(true)
    setStatus('Thinking...')
    scrollToBottom()

    try {
      const data = await askQuestion(query)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          answer: data.answer,
          citations: data.citations,
          confidenceScore: data.confidence_score,
          needsCaveat: data.needs_caveat,
          originalQuery: data.original_query,
          correctedQuery: data.corrected_query,
          queryWasCorrected: data.query_was_corrected,
        },
      ])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', error: err.message }])
    } finally {
      setStatus('')
      setSending(false)
      scrollToBottom()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendQuery()
    }
  }

  return (
    <main id="chatPanel">
      <div className="chat-header">
        <h2>Chat</h2>
      </div>

      <div id="messages" ref={messagesRef}>
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div className="msg user" key={i}>
              <div className="bubble bubble-plain">{msg.text}</div>
            </div>
          ) : (
            <AssistantMessage key={i} {...msg} />
          )
        )}
      </div>

      <div id="status">{status}</div>

      <div id="composer">
        <textarea
          rows={1}
          placeholder="Ask about an issue... (Enter to send, Shift+Enter for a new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button onClick={sendQuery} disabled={sending}>
          Send
        </button>
      </div>
    </main>
  )
}
