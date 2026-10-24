/** Un evento del motor, tal como lo envía `/ws/events` (ver ebica/core/events.py). */
export interface EngineEvent {
  id: string
  ts: string
  entity_id: string
  type: string
  payload: Record<string, unknown>
  cause_id: string | null
}

/** Un mensaje del formato OpenAI, como los que lleva `llm.request`. */
export interface ChatMessage {
  role: string
  content: string
}

/** Mensaje recibido por `/ws/chat`. */
export type ChatReply =
  | { type: 'token'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

/** Respuesta de `GET /api/entities`. */
export interface EntityList {
  ids: string[]
  active: string | null
}

/** URL absoluta de un WebSocket del backend, pasando por el proxy de Vite. */
export function wsUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}${path}`
}
