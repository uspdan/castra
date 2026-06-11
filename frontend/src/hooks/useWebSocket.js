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
  const reconnectTimer = useRef(null)
  const unmounted = useRef(false)
  const accessToken = useAuthStore((s) => s.accessToken)

  const connect = useCallback(() => {
    // Read the token from localStorage rather than the captured
    // store value — the axios 401 interceptor refreshes the token
    // in localStorage without going through the store, so the
    // closure copy can be stale by the time we reconnect.
    const token = localStorage.getItem('access_token')
    if (!token || unmounted.current) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/ws`

    // R11 audit finding — pass auth via Sec-WebSocket-Protocol
    // subprotocol so the JWT stays out of the URL (and out of
    // uvicorn / nginx access logs). The server reflects the
    // matching subprotocol back in its handshake response.
    setConnectionState('connecting')
    const ws = new WebSocket(url, [`siege-auth.${token}`])
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
      } catch {
        // Non-JSON frames are ignored by design.
      }
    }

    ws.onclose = async (event) => {
      setConnectionState('disconnected')
      wsRef.current = null
      if (unmounted.current) return

      // 4001 = server rejected the token (expired/invalid). Get a
      // fresh access token before reconnecting, otherwise the
      // backoff loop just replays the dead token forever and live
      // updates stay broken for the rest of the session.
      if (event.code === 4001) {
        try {
          await useAuthStore.getState().refreshAccessToken()
        } catch {
          // Refresh token gone too — stop; the axios interceptor
          // handles the redirect to /login on the next API call.
          return
        }
      }

      const delay = Math.min(reconnectDelay.current, 30000)
      reconnectDelay.current *= 2
      reconnectTimer.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    unmounted.current = false
    if (accessToken) connect()
    return () => {
      unmounted.current = true
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, accessToken])

  return { connectionState, lastMessage }
}
