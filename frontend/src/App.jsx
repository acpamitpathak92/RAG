import { useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import AboutModal from './components/AboutModal'
import { InfoIcon } from './components/Icons'
import ubsLogo from './assets/ubs-logo.svg'
import './App.css'

export default function App() {
  const [showAbout, setShowAbout] = useState(false)

  return (
    <>
      <header>
        <div className="header-spacer">
          <img src={ubsLogo} alt="UBS logo" className="ubs-logo" />
        </div>
        <div className="header-title">
          <h1>Issue RAG</h1>
          <div className="subtitle">Ask questions about your ingested knowledge base</div>
        </div>
        <div className="header-actions">
          <button className="about-btn" onClick={() => setShowAbout(true)}>
            <InfoIcon /> About
          </button>
        </div>
      </header>
      <div className="layout">
        <Sidebar />
        <ChatPanel />
      </div>
      {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
    </>
  )
}
