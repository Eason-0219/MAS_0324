import { useState, useEffect, useCallback } from 'react'

export function useStats(interval = 10000) {
  const [stats, setStats] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/stats')
      setStats(await res.json())
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, interval)
    return () => clearInterval(t)
  }, [refresh, interval])

  return { stats, refresh }
}
