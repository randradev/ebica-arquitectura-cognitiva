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
  active_name: string | null
}

/**
 * Respuesta de `GET /api/conversation`: los intercambios guardados con la
 * persona que habla ahora (CP8, un hilo por persona).
 */
export interface ConversationResponse {
  entity_id: string | null
  person: { id: string; name: string } | null
  turns: { user: string; entity: string; ts: string; person_id: string | null }[]
}

/** Lo que la entidad sabe de una persona (`PartnerModel.summary()`, CP8). */
export interface PersonSummary {
  id: string
  name: string
  primary: boolean
  trust: number
  n: number
  first_met: string | null
  last_seen: string | null
  valence_mean: number
  arousal_mean: number
  top_topics: string[]
  top_sensitive: string[]
}

/** Respuesta de `GET /api/people`: las personas conocidas y quién habla. */
export interface PeopleResponse {
  active: string | null
  // False sin memoria: entonces solo existe la persona principal.
  can_create: boolean
  people: PersonSummary[]
}

/** URL absoluta de un WebSocket del backend, pasando por el proxy de Vite. */
export function wsUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}${path}`
}
