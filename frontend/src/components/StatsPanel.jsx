import { useState, useEffect } from 'react'

export default function StatsPanel({ stats, onReset }) {
  if (!stats) return (
    <div style={{
      flex: 1, padding: 18,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--text-dim)', fontSize: 12,
    }}>
      <div style={{
        width: 24, height: 24, borderRadius: '50%',
        border: '2px solid var(--border)',
        borderTopColor: 'var(--accent)',
        animation: 'spin 1s linear infinite',
        marginRight: 10,
      }} />
      載入統計中...
    </div>
  )

  const agentEntries = Object.entries(stats.agent_stats || {}).sort((a, b) => b[1] - a[1])
  const langEntries = Object.entries(stats.language_stats || {})
  const totalReq = stats.total_requests || 0

  return (
    <div style={{
      flex: 1, padding: 18, overflowY: 'auto',
      display: 'flex', flexDirection: 'column', gap: 16,
      animation: 'fadeIn .4s ease',
    }}>
      {/* 標題 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{
          fontSize: 11, color: 'var(--text-dim)', fontWeight: 600,
          letterSpacing: 1.5, textTransform: 'uppercase',
        }}>
          📊 數據面板
        </div>
        <button onClick={onReset} style={{
          fontSize: 10, padding: '4px 10px', borderRadius: 8,
          border: '1px solid var(--border)', background: 'transparent',
          color: 'var(--text-dim)', cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'all .2s',
        }}>
          重置
        </button>
      </div>

      {/* 主要指標 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <StatCard
          label="總請求"
          value={totalReq}
          gradient="linear-gradient(135deg, rgba(124,108,255,.12), rgba(124,108,255,.04))"
          accentColor="var(--accent)"
        />
        <StatCard
          label="平均延遲"
          value={`${stats.avg_latency_ms || 0}ms`}
          gradient="linear-gradient(135deg, rgba(0,229,176,.12), rgba(0,229,176,.04))"
          accentColor="var(--accent2)"
        />
      </div>

      {/* Agent 分佈 */}
      {agentEntries.length > 0 && (
        <div>
          <SectionTitle>Agent 分佈</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {agentEntries.map(([agent, count]) => (
              <BarRow
                key={agent}
                label={agent}
                value={count}
                total={totalReq}
                color={AGENT_BAR_COLORS[agent] || 'var(--accent)'}
              />
            ))}
          </div>
        </div>
      )}

      {/* 語言分佈 */}
      {langEntries.length > 0 && (
        <div>
          <SectionTitle>語言分佈</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {langEntries.map(([lang, count]) => (
              <BarRow
                key={lang}
                label={LANG_LABELS[lang] || lang}
                value={count}
                total={totalReq}
                color="var(--accent2)"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


const AGENT_BAR_COLORS = {
  robot: 'var(--agent-robot)',
  sop: 'var(--agent-sop)',
  safety: 'var(--agent-safety)',
  troubleshoot: 'var(--agent-troubleshoot)',
  mcp: 'var(--agent-mcp)',
  chat: 'var(--agent-chat)',
}

const LANG_LABELS = {
  zh: '中文',
  en: 'English',
  vi: 'Tiếng Việt',
  id: 'Bahasa',
}


function SectionTitle({ children }) {
  return (
    <div style={{
      fontSize: 11, color: 'var(--text-dim)', marginBottom: 8,
      fontWeight: 500, letterSpacing: '.5px',
    }}>
      {children}
    </div>
  )
}


function StatCard({ label, value, gradient, accentColor }) {
  return (
    <div style={{
      padding: '14px 14px',
      borderRadius: 12,
      background: gradient,
      border: '1px solid var(--border)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <AnimatedNumber value={value} color={accentColor} />
      <div style={{
        fontSize: 10, color: 'var(--text-dim)', marginTop: 4, fontWeight: 500,
      }}>
        {label}
      </div>
    </div>
  )
}


function AnimatedNumber({ value, color }) {
  const [display, setDisplay] = useState(value)

  useEffect(() => {
    setDisplay(value)
  }, [value])

  return (
    <div style={{
      fontSize: 22, fontWeight: 700, color,
      fontFamily: "'JetBrains Mono', monospace",
      letterSpacing: '-0.5px',
    }}>
      {display}
    </div>
  )
}


function BarRow({ label, value, total, color }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0

  return (
    <div>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, marginBottom: 4,
      }}>
        <span style={{ color: 'var(--text)', fontWeight: 500 }}>{label}</span>
        <span style={{
          color: 'var(--text-dim)',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
        }}>
          {value} ({pct}%)
        </span>
      </div>
      <div style={{
        height: 5, background: 'var(--surface3)', borderRadius: 3,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 60%, white))`,
          borderRadius: 3,
          transition: 'width .6s cubic-bezier(.4,0,.2,1)',
          boxShadow: `0 0 6px color-mix(in srgb, ${color} 40%, transparent)`,
        }} />
      </div>
    </div>
  )
}
