import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket({ onThinking, onResult, onError }) {
  const ws = useRef(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(3000)

  // 用 ref 存 callbacks，避免 useEffect 依賴變化導致重連
  const cbRef = useRef({ onThinking, onResult, onError })
  useEffect(() => {
    cbRef.current = { onThinking, onResult, onError }
  })

  useEffect(() => {
    let destroyed = false

    function connect() {
      if (destroyed) return
      const socket = new WebSocket('ws://localhost:8000/ws/chat')

      socket.onopen = () => {
        if (destroyed) { socket.close(); return }
        setConnected(true)
        reconnectDelay.current = 3000
      }

      socket.onclose = () => {
        setConnected(false)
        if (!destroyed) {
          reconnectTimer.current = setTimeout(connect, reconnectDelay.current)
          reconnectDelay.current = Math.min(reconnectDelay.current * 1.5, 15000)
        }
      }

      socket.onerror = () => socket.close()

      socket.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.type === 'thinking') cbRef.current.onThinking?.(data)
        else if (data.type === 'result') cbRef.current.onResult?.(data)
        else if (data.type === 'error') cbRef.current.onError?.(data.message)
      }

      ws.current = socket
    }

    connect()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, []) // 空依賴，只跑一次

  const sendMessage = useCallback((text) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ message: text }))
    }
  }, [])

  return { sendMessage, connected }
}
