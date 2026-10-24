import { useEffect, useState } from 'react'
import { type EngineEvent, wsUrl } from './types'

// CONSTANTE: máximo de eventos en memoria. El registro completo está en el
// JSONL del disco; la consola solo muestra los recientes para no crecer sin límite.
const MAX_EVENTS = 500

// CONSTANTE: espera antes de reintentar si el backend se cae o reinicia.
const RECONNECT_MS = 2000

/**
 * Se suscribe a `/ws/events` y devuelve los eventos recibidos (el más nuevo
 * primero) y si la conexión está activa. Reconecta sola si se corta.
 */
export function useEvents(): { events: EngineEvent[]; connected: boolean } {
  const [events, setEvents] = useState<EngineEvent[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: number | undefined
    let stopped = false

    /** Abre la conexión y programa un reintento cuando se cierra. */
    function connect(): void {
      socket = new WebSocket(wsUrl('/ws/events'))
      socket.onopen = () => setConnected(true)
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as EngineEvent
        setEvents((previous) => [event, ...previous].slice(0, MAX_EVENTS))
      }
      socket.onclose = () => {
        setConnected(false)
        if (!stopped) retry = window.setTimeout(connect, RECONNECT_MS)
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retry)
      socket?.close()
    }
  }, [])

  return { events, connected }
}
