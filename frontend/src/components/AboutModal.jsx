const INGESTION_STEPS = [
  'Knowledge source\n(.md / .pdf)',
  'Parsing',
  'Cleaning',
  'Chunking\n(parent-child)',
  'Embedding\n(AIaaS)',
  'SQLite + sqlite-vec\n(storage)',
]

const QUERY_STEPS = [
  'Your question',
  'Query cleanup\n(typos, grammar)',
  'Query embedding\n(AIaaS)',
  'Hybrid retrieval\n(vector + keyword)',
  'Reranking\n(AIaaS)',
  'Grounded generation\n(AIaaS, evidence-only)',
  'Citations +\nconfidence',
  'Answer',
]

function FlowRow({ steps }) {
  return (
    <div className="flow-row">
      {steps.map((step, i) => (
        <div className="flow-step-wrap" key={i}>
          <div className="flow-step">
            {step.split('\n').map((line, j) => (
              <div key={j}>{line}</div>
            ))}
          </div>
          {i < steps.length - 1 && <div className="flow-arrow">→</div>}
        </div>
      ))}
    </div>
  )
}

export default function AboutModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal about-modal">
        <h3>How this works</h3>

        <p className="about-lead">
          A local Retrieval-Augmented Generation system. Documents are ingested once; every
          question runs the query pipeline fresh, over whatever is currently in the knowledge base.
          Every embedding, reranking, and generation call is served by the internal UBS
          <strong> AIaaS</strong> gateway — the only LLM/embedding provider this system uses.
        </p>

        <div className="flow-section">
          <div className="flow-label">Ingestion — runs once per document</div>
          <FlowRow steps={INGESTION_STEPS} />
        </div>

        <div className="flow-section">
          <div className="flow-label">Query — runs every question</div>
          <FlowRow steps={QUERY_STEPS} />
        </div>

        <p className="about-note">
          Answers are generated <strong>only</strong> from retrieved evidence, with every claim
          traceable back to a real chunk in a real document. If retrieval doesn't turn up
          anything relevant, you get an honest "not enough evidence" response instead of a guess.
        </p>

        <p className="about-note">
          If your question had typos, grammar issues, or extra spacing, it's cleaned up before
          searching — and if that changes what you typed, you'll see an "Understood as..." note
          above the answer showing both versions, so nothing is silently reinterpreted.
        </p>

        <div className="modal-actions">
          <button className="primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
