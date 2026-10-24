import { useMemo, useState } from 'react'
import type { ChatMessage, EngineEvent } from './types'

/** Hora local HH:MM:SS de un evento (el `ts` viene en UTC). */
function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('es-CL', { hour12: false })
}

/** Resumen de una línea para la cabecera de cada evento. */
function summarize(event: EngineEvent): string {
  const payload = event.payload
  if (typeof payload.text === 'string') return payload.text
  if (typeof payload.partial_text === 'string') return `(parcial) ${payload.partial_text}`
  if (typeof payload.message === 'string') return payload.message
  if (typeof payload.name === 'string') return payload.name
  if (typeof payload.preset === 'string') return `preset ${payload.preset}`
  return ''
}

/**
 * El prompt exacto de un `llm.request`: cada mensaje con su rol y su texto
 * completo, tal como lo recibió el modelo (§8.3, "PROMPT EXACTO").
 */
function PromptView({ event }: { event: EngineEvent }) {
  const body = event.payload.body as { messages?: ChatMessage[] } | undefined
  return (
    <div className="prompt">
      {(body?.messages ?? []).map((message, index) => (
        <div key={index} className="prompt-message">
          <span className="role">{message.role}</span>
          <pre>{message.content}</pre>
        </div>
      ))}
    </div>
  )
}

/** Registro de eventos en vivo, filtrable por tipo; se expande al hacer clic. */
export function EventLog({ events, connected }: { events: EngineEvent[]; connected: boolean }) {
  const [typeFilter, setTypeFilter] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const types = useMemo(() => [...new Set(events.map((event) => event.type))].sort(), [events])
  const visible = typeFilter ? events.filter((event) => event.type === typeFilter) : events

  return (
    <section className="event-log">
      <header className="row">
        <span className={connected ? 'status ok' : 'status off'}>
          {connected ? '● eventos en vivo' : '○ desconectado'}
        </span>
        <select value={typeFilter} onChange={(change) => setTypeFilter(change.target.value)}>
          <option value="">todos los tipos</option>
          {types.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </header>
      <ul>
        {visible.map((event) => (
          <li key={event.id} className={`event ${event.type.split('.')[0]}`}>
            <button className="event-head" onClick={() => setExpanded(expanded === event.id ? null : event.id)}>
              <span className="time">{formatTime(event.ts)}</span>
              <span className="type">{event.type}</span>
              <span className="summary">{summarize(event)}</span>
            </button>
            {expanded === event.id && (
              <div className="event-body">
                {event.type === 'llm.request' && <PromptView event={event} />}
                <pre>{JSON.stringify(event, null, 2)}</pre>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
