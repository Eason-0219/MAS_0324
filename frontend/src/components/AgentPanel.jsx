import { useEffect, useState } from 'react'

const AGENTS = [
  { key: 'robot',        icon: '🤖', label: 'Robot',        color: 'var(--agent-robot)' },
  { key: 'sop',          icon: '📋', label: 'SOP',          color: 'var(--agent-sop)' },
  { key: 'safety',       icon: '🛡️', label: 'Safety',       color: 'var(--agent-safety)' },
  { key: 'troubleshoot', icon: '🔧', label: 'Troubleshoot', color: 'var(--agent-troubleshoot)' },
  { key: 'mcp',          icon: '🌐', label: 'MCP',          color: 'var(--agent-mcp)' },
  { key: 'chat',         icon: '💬', label: 'Chat',         color: 'var(--agent-chat)' },
]

export default function AgentPanel({ lastState }) {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    const fetchStatus = () =>
      fetch('http://localhost:8000/api/status')
        .then(r => r.json())
        .then(setStatus)
        .catch(() => {})
    fetchStatus()
    const t = setInterval(fetchStatus, 5000)
    return () => clearInterval(t)
  }, [])

  const activeRoute = lastState?.route

  return (
    <div style={{
      padding: 18,
      borderBottom: '1px solid var(--border)',
      animation: 'fadeIn .4s ease',
    }}>
      {/* 標題 */}
      <div style={{
        fontSize: 11,
        color: 'var(--text-dim)',
        marginBottom: 14,
        fontWeight: 600,
        letterSpacing: 1.5,
        textTransform: 'uppercase',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: activeRoute ? 'var(--success)' : 'var(--text-dim)',
          boxShadow: activeRoute ? '0 0 6px var(--success)' : 'none',
          display: 'inline-block',
        }} />
        Agent 面板
      </div>

      {/* Agent 網格 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {AGENTS.map(a => (
          <AgentCard key={a.key} agent={a} active={activeRoute === a.key} />
        ))}
      </div>

      {/* 中心路由器 */}
      {activeRoute && (
        <div style={{
          marginTop: 14,
          padding: '10px 14px',
          borderRadius: 10,
          background: 'var(--surface2)',
          border: '1px solid var(--border)',
          animation: 'fadeSlideUp .3s ease',
        }}>
          <div style={{
            fontSize: 10, color: 'var(--text-dim)',
            marginBottom: 8, fontWeight: 600,
          }}>
            最後路由
          </div>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 5,
            fontSize: 12,
          }}>
            <InfoRow label="Agent" value={lastState.route} accent />
            <InfoRow label="模型" value={lastState.model_used} />
            <InfoRow label="延遲" value={`${lastState.latency_ms?.toFixed(0)}ms`} />
            {lastState.tool_name && <InfoRow label="工具" value={lastState.tool_name} />}
            {lastState.redirect_reason && (
              <InfoRow label="二次路由" value={lastState.redirect_reason} warn />
            )}
            {lastState.modbus_result && (
              <InfoRow
                label="Modbus"
                value={`Reg=${lastState.modbus_result.register} Val=${lastState.modbus_result.value}`}
                accent2
              />
            )}
          </div>
        </div>
      )}

      {/* 操作員 */}
      {status?.context?.operator_name && (
        <div style={{
          marginTop: 10, padding: '10px 14px',
          borderRadius: 10,
          background: 'rgba(0,229,176,.06)',
          border: '1px solid rgba(0,229,176,.15)',
          fontSize: 12,
          animation: 'fadeIn .3s ease',
        }}>
          <span style={{ color: 'var(--accent2)', fontWeight: 600 }}>
            👤 {status.context.operator_name}
          </span>
          {status.context.operator_height && (
            <span style={{ color: 'var(--text-dim)' }}>
              {' '}· {status.context.operator_height}cm · 設定檔 {status.context.height_profile}
            </span>
          )}
        </div>
      )}

      {/* Checklist */}
      {status?.context?.checklist_active && (
        <div style={{
          marginTop: 8, padding: '8px 14px',
          borderRadius: 10,
          background: 'rgba(255,179,71,.06)',
          border: '1px solid rgba(255,179,71,.2)',
          fontSize: 11, color: 'var(--warning)',
          fontWeight: 500,
          animation: 'pulse 2s infinite',
        }}>
          🔒 安全核對清單進行中
        </div>
      )}
    </div>
  )
}


/* ── Agent 卡片 ────────────────────────── */
function AgentCard({ agent, active }) {
  return (
    <div style={{
      padding: '10px 8px',
      borderRadius: 10,
      border: `1.5px solid ${active ? agent.color : 'var(--border)'}`,
      background: active
        ? `color-mix(in srgb, ${agent.color} 10%, transparent)`
        : 'var(--surface2)',
      textAlign: 'center',
      transition: 'all .35s ease',
      boxShadow: active ? `0 0 14px color-mix(in srgb, ${agent.color} 30%, transparent)` : 'none',
      transform: active ? 'scale(1.05)' : 'scale(1)',
      cursor: 'default',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* 激活光暈背景 */}
      {active && (
        <div style={{
          position: 'absolute',
          top: '50%', left: '50%',
          transform: 'translate(-50%,-50%)',
          width: 50, height: 50,
          borderRadius: '50%',
          background: `radial-gradient(circle, color-mix(in srgb, ${agent.color} 20%, transparent), transparent)`,
          pointerEvents: 'none',
        }} />
      )}

      <div style={{
        fontSize: 20,
        position: 'relative',
        filter: active ? `drop-shadow(0 0 6px ${agent.color})` : 'none',
      }}>
        {agent.icon}
      </div>
      <div style={{
        fontSize: 10,
        color: active ? agent.color : 'var(--text-dim)',
        marginTop: 4,
        fontWeight: active ? 600 : 400,
        letterSpacing: '.3px',
        position: 'relative',
      }}>
        {agent.label}
      </div>
    </div>
  )
}


/* ── 資訊行 ────────────────────────────── */
function InfoRow({ label, value, accent, accent2, warn }) {
  const color = accent ? 'var(--accent-light)' : accent2 ? 'var(--accent2)' : warn ? 'var(--warning)' : 'var(--text)'
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
    }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span style={{ color, fontWeight: 500, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
        {value}
      </span>
    </div>
  )
}
