import { useState, useRef, useEffect } from 'react'

const AGENT_COLORS = {
  robot: 'var(--agent-robot)',
  sop: 'var(--agent-sop)',
  safety: 'var(--agent-safety)',
  troubleshoot: 'var(--agent-troubleshoot)',
  mcp: 'var(--agent-mcp)',
  chat: 'var(--agent-chat)',
}

const AGENT_ICONS = {
  robot: '🤖', sop: '📋', safety: '🛡️',
  troubleshoot: '🔧', mcp: '🌐', chat: '💬',
}

export default function ChatPanel({ messages, thinking, onSend }) {
  const [input, setInput] = useState('')
  const [inputFocused, setInputFocused] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const submit = () => {
    const text = input.trim()
    if (!text) return
    onSend(text)
    setInput('')
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── 訊息列表 ──────────────────────────────── */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '20px 24px',
        display: 'flex', flexDirection: 'column', gap: 16,
        background: `
          radial-gradient(ellipse at 20% 50%, rgba(124,108,255,.03) 0%, transparent 60%),
          radial-gradient(ellipse at 80% 80%, rgba(0,229,176,.02) 0%, transparent 60%),
          var(--bg2)
        `,
      }}>
        {messages.length === 0 && <WelcomeScreen />}

        {messages.map((msg, i) => (
          <Message key={i} msg={msg} index={i} />
        ))}

        {thinking && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>

      {/* ── 輸入區 ──────────────────────────────── */}
      <div className="glass-strong" style={{
        padding: '14px 20px',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        gap: 10,
        flexShrink: 0,
      }}>
        <div style={{
          flex: 1,
          position: 'relative',
          borderRadius: 12,
          border: `1.5px solid ${inputFocused ? 'var(--accent)' : 'var(--border)'}`,
          background: 'var(--surface2)',
          transition: 'border-color .25s ease, box-shadow .25s ease',
          boxShadow: inputFocused ? '0 0 0 3px rgba(124,108,255,.12)' : 'none',
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit()}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            placeholder="輸入訊息... (Enter 送出)"
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              borderRadius: 12,
              padding: '12px 16px',
              color: 'var(--text)',
              fontSize: 14,
              fontFamily: 'inherit',
              outline: 'none',
            }}
          />
        </div>
        <button
          onClick={submit}
          disabled={!input.trim()}
          style={{
            padding: '12px 22px',
            borderRadius: 12,
            border: 'none',
            background: input.trim()
              ? 'linear-gradient(135deg, var(--accent), var(--accent-dark))'
              : 'var(--surface2)',
            color: input.trim() ? 'white' : 'var(--text-dim)',
            cursor: input.trim() ? 'pointer' : 'default',
            fontSize: 14,
            fontWeight: 600,
            fontFamily: 'inherit',
            transition: 'all .25s ease',
            boxShadow: input.trim() ? 'var(--shadow-glow)' : 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          送出
          <span style={{ fontSize: 16 }}>↗</span>
        </button>
      </div>
    </div>
  )
}


/* ── 歡迎畫面 ──────────────────────────────── */
function WelcomeScreen() {
  const suggestions = [
    { icon: '🤖', text: '伸出手臂' },
    { icon: '📋', text: '第三步是什麼' },
    { icon: '🌐', text: '現在幾點' },
    { icon: '🛡️', text: '我要進產線了' },
  ]

  return (
    <div style={{
      margin: 'auto', textAlign: 'center',
      animation: 'fadeSlideUp .6s ease',
    }}>
      <div style={{
        fontSize: 56, marginBottom: 16,
        filter: 'drop-shadow(0 0 20px rgba(124,108,255,.4))',
      }}>
        🤖
      </div>
      <div style={{
        fontSize: 22, fontWeight: 700, marginBottom: 6,
        background: 'linear-gradient(135deg, var(--accent-light), var(--accent2))',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}>
        你好！我是 CoinAI
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 28 }}>
        你的顯示卡組裝智慧助手 · 多語言支援 · 語音互動
      </div>

      {/* 快速建議 */}
      <div style={{
        display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap',
      }}>
        {suggestions.map((s, i) => (
          <div key={i} style={{
            padding: '10px 18px',
            borderRadius: 20,
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            fontSize: 13,
            color: 'var(--text-sub)',
            cursor: 'default',
            transition: 'all .2s',
            animation: `fadeSlideUp .5s ease ${i * 0.1}s both`,
          }}>
            <span style={{ marginRight: 6 }}>{s.icon}</span>
            {s.text}
          </div>
        ))}
      </div>
    </div>
  )
}


/* ── 訊息 ──────────────────────────────── */
function Message({ msg, index }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'
  const meta = msg.meta
  const agentColor = meta ? (AGENT_COLORS[meta.route] || 'var(--text-dim)') : 'var(--text-dim)'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      gap: 6,
      animation: `fadeSlideUp .35s ease ${Math.min(index * 0.05, 0.3)}s both`,
    }}>
      {/* 氣泡 */}
      <div style={{
        maxWidth: '78%',
        display: 'flex',
        alignItems: 'stretch',
        gap: 0,
      }}>
        {/* Agent 色條 (助手訊息) */}
        {!isUser && !isError && meta && (
          <div style={{
            width: 3,
            borderRadius: 3,
            background: agentColor,
            marginRight: 10,
            boxShadow: `0 0 6px ${agentColor}`,
            flexShrink: 0,
          }} />
        )}

        <div style={{
          padding: '12px 16px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: isUser
            ? 'linear-gradient(135deg, var(--accent), var(--accent-dark))'
            : isError
              ? 'rgba(255,107,107,.08)'
              : 'var(--surface2)',
          border: isError ? '1px solid rgba(255,107,107,.3)' : '1px solid transparent',
          fontSize: 14,
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          color: isUser ? 'white' : isError ? 'var(--danger)' : 'var(--text)',
          boxShadow: isUser ? '0 4px 12px rgba(124,108,255,.2)' : 'var(--shadow-sm)',
        }}>
          {msg.text}
        </div>
      </div>

      {/* 元資訊標籤 */}
      {meta && (
        <div style={{
          display: 'flex', gap: 5, flexWrap: 'wrap',
          paddingLeft: !isUser ? 14 : 0,
        }}>
          <Tag color={agentColor}>
            {AGENT_ICONS[meta.route] || '?'} {meta.route}
          </Tag>
          <Tag color="var(--text-dim)">{meta.model}</Tag>
          <Tag color="var(--text-dim)">⏱ {meta.latency?.toFixed(0)}ms</Tag>
          {meta.tool && <Tag color="var(--info)">🔧 {meta.tool}</Tag>}
          {meta.redirect && <Tag color="var(--warning)">🔄 {meta.redirect}</Tag>}
        </div>
      )}
    </div>
  )
}


function Tag({ color, children }) {
  return (
    <span style={{
      fontSize: 10,
      padding: '3px 9px',
      borderRadius: 12,
      background: `color-mix(in srgb, ${color} 12%, transparent)`,
      border: `1px solid color-mix(in srgb, ${color} 20%, transparent)`,
      color: color,
      fontWeight: 500,
      letterSpacing: '.3px',
    }}>
      {children}
    </span>
  )
}


function ThinkingBubble() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      animation: 'fadeSlideUp .3s ease',
    }}>
      {/* 色條 */}
      <div style={{
        width: 3, height: 32,
        borderRadius: 3,
        background: 'var(--accent)',
        boxShadow: '0 0 6px var(--accent)',
        animation: 'pulse 1.5s infinite',
      }} />

      <div style={{
        padding: '12px 18px',
        borderRadius: '16px 16px 16px 4px',
        background: 'var(--surface2)',
        display: 'flex',
        gap: 6,
        alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent)',
            animation: `dotBounce 1.4s ${i * 0.2}s infinite`,
          }} />
        ))}
        <span style={{
          marginLeft: 8, fontSize: 12, color: 'var(--text-dim)',
        }}>
          思考中...
        </span>
      </div>
    </div>
  )
}
