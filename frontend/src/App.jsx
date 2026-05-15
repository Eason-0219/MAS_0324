import { useState, useCallback } from 'react'
import ChatPanel from './components/ChatPanel'
import AgentPanel from './components/AgentPanel'
import StatsPanel from './components/StatsPanel'
import VoiceOrb from './components/VoiceOrb'
import WakePanel from './components/WakePanel'
import { useWebSocket } from './hooks/useWebSocket'
import { useStats } from './hooks/useStats'

export default function App() {
  const [messages, setMessages] = useState([])
  const [thinking, setThinking] = useState(false)
  const [lastState, setLastState] = useState(null)
  const [voiceMode, setVoiceMode] = useState(false)
  const [wakeActive, setWakeActive] = useState(false) // 喚醒詞觸發中

  const { sendMessage, connected } = useWebSocket({
    onThinking: () => setThinking(true),
    onResult: (data) => {
      setThinking(false)
      setLastState(data)
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.response,
        meta: {
          route: data.route,
          model: data.model_used,
          latency: data.latency_ms,
          tool: data.tool_name,
          lang: data.detected_language,
          redirect: data.redirect_reason,
        },
        ts: Date.now(),
      }])
    },
    onError: (msg) => {
      setThinking(false)
      setMessages(prev => [...prev, { role: 'error', text: msg, ts: Date.now() }])
    },
  })

  const { stats, refresh: refreshStats } = useStats()

  const handleSend = useCallback((text) => {
    if (!text.trim()) return
    setMessages(prev => [...prev, { role: 'user', text, ts: Date.now() }])
    sendMessage(text)
    setTimeout(refreshStats, 1500)
  }, [sendMessage, refreshStats])

  // 喚醒詞事件處理
  const handleWakeActivated = useCallback(() => {
    setWakeActive(true)
    setVoiceMode(true) // 進入語音 Orb，透過 autoStart 自動啟動麥克風
  }, [])

  const handleWakeResponse = useCallback((msg) => {
    if (msg.type === 'wake_transcript') {
      setMessages(prev => [...prev, { role: 'user', text: msg.text, ts: Date.now(), meta: { source: 'wake' } }])
    } else if (msg.response) {
      setLastState(msg)
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: msg.response,
        ts: Date.now(),
        meta: { route: msg.route, model: msg.model_used, latency: msg.latency_ms, tool: msg.tool_name, source: 'wake' },
      }])
      setTimeout(refreshStats, 1500)
    }
  }, [refreshStats])

  const handleWakeIdle = useCallback(() => {
    setWakeActive(false)
  }, [])

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
      background: 'var(--bg)',
    }}>
      {/* ── 左側：主區域 ──────────────────────────── */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Header
          connected={connected}
          voiceMode={voiceMode}
          onToggleVoice={() => {
            if (voiceMode) setWakeActive(false); // 關閉 VoiceOrb 時清除 wake 狀態
            setVoiceMode(v => !v);
          }}
        />

        {/* 思考中進度條 */}
        {thinking && (
          <div style={{
            height: 2,
            background: 'linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite linear',
            flexShrink: 0,
          }} />
        )}

        {/* 喚醒詞觸發提示條 */}
        {wakeActive && (
          <div style={{
            padding: '6px 20px',
            background: 'linear-gradient(90deg, rgba(124,108,255,.15), rgba(0,229,176,.1))',
            borderBottom: '1px solid rgba(124,108,255,.2)',
            fontSize: 12,
            color: 'var(--accent-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
            animation: 'pulse 1.5s infinite',
          }}>
            <span style={{ fontSize: 14 }}>🎙️</span>
            喚醒詞已觸發，正在聆聽...
          </div>
        )}

        {voiceMode
          ? <VoiceOrb 
              autoStart={wakeActive}
              onClose={() => {
                setVoiceMode(false);
                setWakeActive(false);
              }}
              onResponse={(userMsg, assistantMsg) => {
              setMessages(prev => [...prev,
                { role: 'user', text: userMsg.content, ts: Date.now() },
                { role: 'assistant', text: assistantMsg.content, ts: Date.now(),
                  meta: { route: assistantMsg.route, model: assistantMsg.model_used,
                    latency: assistantMsg.latency_ms, tool: assistantMsg.tool_name }
                },
              ]);
              setLastState({ route_decision: assistantMsg.route, model_used: assistantMsg.model_used,
                latency_ms: assistantMsg.latency_ms, tool_name: assistantMsg.tool_name });
              setTimeout(refreshStats, 1500);
            }} />
          : <ChatPanel messages={messages} thinking={thinking} onSend={handleSend} />
        }
      </div>

      {/* ── 右側：面板 ──────────────────────────────── */}
      <aside style={{
        width: 330,
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--surface)',
        animation: 'slideInRight .4s ease',
      }}>
        <AgentPanel lastState={lastState} />
        <StatsPanel stats={stats} onReset={async () => {
          await fetch('http://localhost:8000/api/stats/reset', { method: 'DELETE' })
          refreshStats()
        }} />
        <WakePanel
          onWakeActivated={handleWakeActivated}
          onWakeResponse={handleWakeResponse}
          onWakeIdle={handleWakeIdle}
        />
      </aside>
    </div>
  )
}


/* ── Header ─────────────────────────────────── */
function Header({ connected, voiceMode, onToggleVoice }) {
  return (
    <header className="glass-strong" style={{
      padding: '14px 24px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      flexShrink: 0,
      zIndex: 10,
    }}>
      {/* Logo */}
      <div style={{
        width: 40, height: 40,
        borderRadius: 12,
        background: 'linear-gradient(135deg, var(--accent), var(--accent2))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20,
        boxShadow: '0 0 16px rgba(124,108,255,.3)',
        animation: 'breathe 3s ease-in-out infinite',
      }}>
        🤖
      </div>

      <div>
        <div style={{
          fontWeight: 700,
          fontSize: 17,
          letterSpacing: '.5px',
          background: 'linear-gradient(135deg, var(--accent-light), var(--accent2))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          CoinAI
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 400 }}>
          Multi-Agent System · MAS
        </div>
      </div>

      {/* 右側控制區 */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* 連線狀態 */}
        <StatusDot connected={connected} />

        {/* 語音切換按鈕 */}
        <button onClick={onToggleVoice} style={{
          padding: '7px 16px',
          borderRadius: 20,
          border: `1px solid ${voiceMode ? 'var(--accent2)' : 'var(--border)'}`,
          background: voiceMode
            ? 'linear-gradient(135deg, rgba(0,229,176,.15), rgba(0,229,176,.05))'
            : 'transparent',
          color: voiceMode ? 'var(--accent2)' : 'var(--text-sub)',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 500,
          transition: 'all .25s ease',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontFamily: 'inherit',
        }}>
          <span style={{ fontSize: 14 }}>{voiceMode ? '🎙️' : '⌨️'}</span>
          {voiceMode ? '語音模式' : '文字模式'}
        </button>
      </div>
    </header>
  )
}


function StatusDot({ connected }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      fontSize: 11,
      color: 'var(--text-dim)',
      fontWeight: 500,
    }}>
      <div style={{
        width: 8, height: 8,
        borderRadius: '50%',
        background: connected ? 'var(--success)' : 'var(--danger)',
        boxShadow: connected ? '0 0 8px var(--success)' : '0 0 8px var(--danger)',
        animation: connected ? 'pulse 2s infinite' : 'none',
      }} />
      {connected ? '已連線' : '離線'}
    </div>
  )
}
