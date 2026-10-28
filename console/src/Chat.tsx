import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { type ChatReply, type ConversationResponse, type PeopleResponse, wsUrl } from './types'

interface Line {
  author: 'usuario' | 'entidad' | 'sistema'
  text: string
}

// Valor del selector que abre el formulario de persona nueva.
const NEW_PERSON = '__nueva__'

/** Pide al backend las personas que conoce la entidad activa y quién habla. */
async function fetchPeople(): Promise<PeopleResponse> {
  const response = await fetch('/api/people')
  if (!response.ok) throw new Error(`Error ${response.status}`)
  return (await response.json()) as PeopleResponse
}

/**
 * Selector «Hablando como» (§8.3, CP8 D1-52): elige a una persona conocida o
 * crea una nueva con nombre. Avisa al chat quién habla ahora.
 */
function PartnerSelector({ activeId, onPartner }: {
  activeId: string
  onPartner: (person: { id: string; name: string } | null) => void
}) {
  const [people, setPeople] = useState<PeopleResponse | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  /** Guarda la lista recibida y avisa al chat quién está activa. */
  const applyPeople = useCallback(
    (data: PeopleResponse) => {
      setPeople(data)
      const active = data.people.find((person) => person.id === data.active)
      onPartner(active ? { id: active.id, name: active.name } : null)
    },
    [onPartner],
  )

  /** Vuelve a pedir la lista tras una acción (elegir o crear). */
  async function refresh(): Promise<void> {
    applyPeople(await fetchPeople())
  }

  // Al cambiar de entidad, se pide su lista de personas.
  useEffect(() => {
    fetchPeople()
      .then(applyPeople)
      .catch(() => setError('No se pudo cargar la lista de personas'))
  }, [activeId, applyPeople])

  /** Elige a una persona conocida (`tom.partner_switched`). */
  async function choose(id: string): Promise<void> {
    setError(null)
    if (id === NEW_PERSON) {
      setCreating(true)
      return
    }
    const response = await fetch(`/api/people/${encodeURIComponent(id)}/activate`, { method: 'POST' })
    if (!response.ok) setError((await response.json()).detail ?? `Error ${response.status}`)
    await refresh()
  }

  /** Crea una persona nueva con nombre y la deja activa (`tom.person_created`). */
  async function create(submit: FormEvent): Promise<void> {
    submit.preventDefault()
    setError(null)
    const response = await fetch('/api/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() }),
    })
    if (!response.ok) {
      const detail = (await response.json()).detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
      return
    }
    setName('')
    setCreating(false)
    await refresh()
  }

  // Una entidad sin personas (sin `primary` y sin memoria) no muestra el selector.
  if (!people || (people.people.length === 0 && !people.can_create)) return null
  return (
    <div className="partner-selector">
      <div className="row">
        <span className="muted">hablando como</span>
        <select value={creating ? NEW_PERSON : people.active ?? ''} onChange={(change) => choose(change.target.value)}>
          {people.active === null && <option value="">—</option>}
          {people.people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
              {person.primary ? ' (principal)' : ''}
            </option>
          ))}
          {people.can_create && <option value={NEW_PERSON}>Nueva persona…</option>}
        </select>
      </div>
      {creating && (
        <form onSubmit={create} className="row">
          <input placeholder="nombre de la persona" value={name} onChange={(change) => setName(change.target.value)}
            autoFocus required />
          <button type="submit" disabled={!name.trim()}>Crear</button>
          <button type="button" onClick={() => setCreating(false)}>Cancelar</button>
        </form>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}

/**
 * Chat con la entidad activa por `/ws/chat`. La respuesta se va escribiendo
 * fragmento a fragmento a medida que el LLM la genera (streaming). Cada
 * persona tiene su propio hilo (CP8): al cambiar de interlocutor se muestra
 * la conversación guardada con esa persona.
 */
export function Chat({ activeId, activeName }: { activeId: string | null; activeName: string | null }) {
  const [lines, setLines] = useState<Line[]>([])
  const [draft, setDraft] = useState('')
  const [waiting, setWaiting] = useState(false)
  const [partner, setPartner] = useState<{ id: string; name: string } | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  // Al abrir la consola, cambiar de entidad o de interlocutor, muestra la
  // conversación guardada con quien habla ahora (`/api/conversation`).
  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    fetch('/api/conversation')
      .then((response) => response.json() as Promise<ConversationResponse>)
      .then((data) => {
        if (cancelled || data.entity_id !== activeId) return
        setLines(data.turns.flatMap((turn) => [
          { author: 'usuario' as const, text: turn.user },
          { author: 'entidad' as const, text: turn.entity },
        ]))
      })
      .catch(() => setLines([{ author: 'sistema', text: 'No se pudo cargar la conversación guardada' }]))
    return () => {
      cancelled = true
    }
  }, [activeId, partner?.id])

  useEffect(() => {
    const socket = new WebSocket(wsUrl('/ws/chat'))
    socket.onmessage = (message) => {
      const reply = JSON.parse(message.data) as ChatReply
      if (reply.type === 'token') {
        // Añade el fragmento a la última línea de la entidad.
        setLines((previous) => {
          const last = previous[previous.length - 1]
          return [...previous.slice(0, -1), { ...last, text: last.text + reply.text }]
        })
      } else if (reply.type === 'done') {
        setWaiting(false)
      } else {
        setLines((previous) => [
          ...previous.filter((line) => line.author !== 'entidad' || line.text !== ''),
          { author: 'sistema', text: reply.message },
        ])
        setWaiting(false)
      }
    }
    socket.onclose = () => setWaiting(false)
    socketRef.current = socket
    return () => socket.close()
  }, [])

  /** Envía el mensaje y prepara una línea vacía donde irá la respuesta. */
  function send(submit: FormEvent): void {
    submit.preventDefault()
    const text = draft.trim()
    const socket = socketRef.current
    if (!text || !socket || socket.readyState !== WebSocket.OPEN) return
    setLines((previous) => [...previous, { author: 'usuario', text }, { author: 'entidad', text: '' }])
    setDraft('')
    setWaiting(true)
    socket.send(JSON.stringify({ text }))
  }

  /** Nombre que se muestra delante de cada línea: la entidad, quien habla o «sistema». */
  function label(author: Line['author']): string {
    if (author === 'entidad') return activeName ?? 'entidad'
    if (author === 'usuario') return partner?.name ?? 'usuario'
    return author
  }

  return (
    <section className="chat">
      {activeId && <PartnerSelector activeId={activeId} onPartner={setPartner} />}
      <div className="lines">
        {/* Sin entidad activa no hay conversación que mostrar. */}
        {(activeId ? lines : []).map((line, index) => (
          <p key={index} className={`line ${line.author}`}>
            <strong>{label(line.author)}:</strong>{' '}
            {line.text || (waiting && index === lines.length - 1 ? '…' : '')}
          </p>
        ))}
      </div>
      <form onSubmit={send} className="row">
        <input value={draft} onChange={(change) => setDraft(change.target.value)}
          placeholder={activeId ? 'Escribe un mensaje' : 'Carga una entidad primero'}
          disabled={!activeId || waiting} />
        <button type="submit" disabled={!activeId || waiting || !draft.trim()}>
          Enviar
        </button>
      </form>
    </section>
  )
}
