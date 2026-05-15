// frontend/src/components/WakePanel.jsx
/**
 * 喚醒詞設定小區塊
 * 顯示在右側面板底部，不影響現有 UI
 */
import { useState, useEffect, useRef, useCallback } from 'react'

const API = 'http://localhost:8000'
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://localhost:8000/ws/wake`

export default function WakePanel({ onWakeActivated, onWakeResponse, onWakeIdle }) {
  const [settings, setSettings] = useState({
    wake_word: '嘿 CoinAI',
    tts_enabled: true,
    listening: false,
  })
  const [wakeState, setWakeState] = useState('idle') // idle | activated | listening | processing
  const [editWord, setEditWord] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const wsRef = useRef(null)

  // 載入設定
  useEffect(() => {
    fetch(`${API}/api/wake/settings`)
      .then(r => r.json())
      .then(d => {
        setSettings(d)
        setEditWord(d.wake_word)
      })
      .catch(() => {})
  }, [])

  // 同步 editWord（非編輯狀態時跟著 settings 更新）
  useEffect(() => {
    if (!editing) setEditWord(settings.wake_word)
  }, [settings.wake_word])

  // WebSocket 訂閱喚醒事件
  useEffect(() => {
    let ws
    let retryTimer
    let active = true
    let ttsChunks = []
    let ttsPlaying = false

    const playTTS = async (chunks) => {
      if (!chunks.length) return
      ttsPlaying = true
      const total = chunks.reduce((s, c) => s + c.byteLength, 0)
      const merged = new Uint8Array(total)
      let offset = 0
      for (const c of chunks) { merged.set(new Uint8Array(c), offset); offset += c.byteLength }
      const blob = new Blob([merged], { type: 'audio/mpeg' })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => { URL.revokeObjectURL(url); ttsPlaying = false }
      audio.onerror = () => { URL.revokeObjectURL(url); ttsPlaying = false }
      try { await audio.play() } catch { ttsPlaying = false }
    }

    const connect = () => {
      if (!active) return
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.onclose = null
        ws.close()
      }

      ws = new WebSocket(WS_URL)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onmessage = (e) => {
        // 二進位 = TTS 音訊 chunk
        if (e.data instanceof ArrayBuffer) {
          ttsChunks.push(e.data)
          return
        }
        try {
          const msg = JSON.parse(e.data)
          switch (msg.type) {
            case 'wake_status':
              setSettings(prev => ({ ...prev, listening: msg.listening, wake_word: msg.wake_word || prev.wake_word }))
              break
            case 'wake_activated':
              setWakeState('activated')
              onWakeActivated?.()
              break
            case 'wake_listening':
              setWakeState('listening')
              break
            case 'wake_processing':
              setWakeState('processing')
              break
            case 'wake_response':
              onWakeResponse?.(msg)
              break
            case 'wake_idle':
              setWakeState('idle')
              onWakeIdle?.()
              break
            case 'wake_transcript':
              onWakeResponse?.({ type: 'wake_transcript', text: msg.text })
              break
            case 'wake_tts_start':
              ttsChunks = []
              break
            case 'wake_tts_end':
              playTTS(ttsChunks)
              ttsChunks = []
              break
          }
        } catch {}
      }

      ws.onclose = () => {
        if (active) retryTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      active = false
      clearTimeout(retryTimer)
      if (ws) { ws.onclose = null; ws.close() }
    }
  }, [])

  const saveWakeWord = useCallback(async () => {
    if (!editWord.trim() || editWord === settings.wake_word) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      const res = await fetch(`${API}/api/wake/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wake_word: editWord.trim() }),
      })
      const data = await res.json()
      setSettings(prev => ({ ...prev, wake_word: data.wake_word, listening: data.listening }))
      setEditWord(data.wake_word)
    } catch {}
    setSaving(false)
    setEditing(false)
  }, [editWord, settings.wake_word])

  const toggleTTS = useCallback(async () => {
    const next = !settings.tts_enabled
    setSettings(prev => ({ ...prev, tts_enabled: next }))
    try {
      await fetch(`${API}/api/wake/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tts_enabled: next }),
      })
    } catch {}
  }, [settings.tts_enabled])

  // 狀態燈顏色
  const dotColor = settings.listening
    ? wakeState === 'idle' ? 'var(--success)' : 'var(--accent)'
    : 'var(--text-dim)'

  const stateLabel = {
    idle: settings.listening ? '監聽中' : '未啟動',
    activated: '已喚醒！',
    listening: '聆聽中...',
    processing: '處理中...',
  }[wakeState]

  return (
    <div style={{
      padding: '14px 18px',
      borderTop: '1px solid var(--border)',
      animation: 'fadeIn .4s ease',
    }}>
      {/* 標題列 */}
      <div style={{
        fontSize: 11,
        color: 'var(--text-dim)',
        marginBottom: 12,
        fontWeight: 600,
        letterSpacing: 1.5,
        textTransform: 'uppercase',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: dotColor,
          boxShadow: settings.listening ? `0 0 6px ${dotColor}` : 'none',
          display: 'inline-block',
          transition: 'all .3s',
          animation: wakeState !== 'idle' ? 'pulse 1s infinite' : 'none',
        }} />
        喚醒詞設定
        <span style={{
          marginLeft: 'auto',
          fontSize: 10,
          color: wakeState !== 'idle' ? 'var(--accent-light)' : 'var(--text-dim)',
          fontWeight: 500,
          letterSpacing: 0,
        }}>
          {stateLabel}
        </span>
      </div>

      {/* 喚醒詞輸入 */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 5 }}>喚醒詞</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={editing ? editWord : settings.wake_word}
            onChange={e => { setEditing(true); setEditWord(e.target.value) }}
            onFocus={() => { setEditing(true); setEditWord(settings.wake_word) }}
            onBlur={saveWakeWord}
            onKeyDown={e => {
              if (e.key === 'Enter') { e.target.blur() }
              if (e.key === 'Escape') { setEditing(false); setEditWord(settings.wake_word) }
            }}
            placeholder="輸入喚醒詞..."
            style={{
              flex: 1,
              background: 'var(--surface2)',
              border: `1px solid ${editing ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 8,
              padding: '6px 10px',
              color: 'var(--text)',
              fontSize: 12,
              fontFamily: 'inherit',
              outline: 'none',
              transition: 'border-color .2s',
            }}
          />
          {editing && (
            <button
              onClick={saveWakeWord}
              disabled={saving}
              style={{
                padding: '6px 10px',
                borderRadius: 8,
                border: 'none',
                background: 'var(--accent)',
                color: '#fff',
                fontSize: 11,
                cursor: 'pointer',
                fontFamily: 'inherit',
                opacity: saving ? 0.6 : 1,
              }}
            >
              {saving ? '...' : '✓'}
            </button>
          )}
        </div>
      </div>

      {/* TTS 開關 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: 12,
        color: 'var(--text-sub)',
      }}>
        <span>語音回應 (TTS)</span>
        <button
          onClick={toggleTTS}
          style={{
            padding: '4px 12px',
            borderRadius: 20,
            border: `1px solid ${settings.tts_enabled ? 'var(--accent2)' : 'var(--border)'}`,
            background: settings.tts_enabled
              ? 'rgba(0,229,176,.15)'
              : 'transparent',
            color: settings.tts_enabled ? 'var(--accent2)' : 'var(--text-dim)',
            fontSize: 11,
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontWeight: 500,
            transition: 'all .2s',
          }}
        >
          {settings.tts_enabled ? 'ON' : 'OFF'}
        </button>
      </div>
    </div>
  )
}
