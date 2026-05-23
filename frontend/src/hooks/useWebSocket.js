import { useEffect, useRef, useState, useCallback } from 'react'
import useAuthStore from '../stores/authStore'
import useLeaderboardStore from '../stores/leaderboardStore'
import useChallengeStore from '../stores/challengeStore'
import useNotificationStore from '../stores/notificationStore'

export default function useWebSocket() {
  const [connectionState, setConnectionState] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)
  const reconnectDelay = useRef(1000)
  const accessToken = useAuthStore((s) => s.accessToken)

  const connect = useCallback(() => {
    if (!accessToken) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/ws`

    // R11 audit finding — pass auth via Sec-WebSocket-Protocol
    // subprotocol so the JWT stays out of the URL (and out of
    // uvicorn / nginx access logs). The server reflects the
    // matching subprotocol back in its handshake response.
    setConnectionState('connecting')
    const ws = new WebSocket(url, [`siege-auth.${accessToken}`])
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionState('connected')
      reconnectDelay.current = 1000
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLastMessage(data)

        if (data.type === 'flag_captured') {
          useLeaderboardStore.getState().fetchLeaderboard()
        } else if (data.type === 'challenge_released') {
          useChallengeStore.getState().fetchChallenges()
        } else if (data.type === 'notification') {
          useNotificationStore.getState().addNotification(data)
          useNotificationStore.getState().fetchUnreadCount()
        }
      } catch {}
    }

    ws.onclose = () => {
      setConnectionState('disconnected')
      wsRef.current = null
      const delay = Math.min(reconnectDelay.current, 30000)
      reconnectDelay.current *= 2
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [accessToken])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return { connectionState, lastMessage }
}
