import { type FormEvent, useEffect, useRef, useState } from 'react'
import { type ChatReply, wsUrl } from './types'

interface Line {
  author: 'usuario' | 'entidad' | 'sistema'
  text: string
}

/**
 * Chat con la entidad activa por `/ws/chat`. La respuesta se va escribiendo
 * fragmento a fragmento a medida que el LLM la genera (streaming).
 */
export function Chat({ activeId, activeName }: { activeId: string | null; activeName: string | null }) {
  const [lines, setLines] = useState<Line[]>([])
  const [draft, setDraft] = useState('')
  const [waiting, setWaiting] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)

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

  return (
    <section className="chat">
      <div className="lines">
        {lines.map((line, index) => (
          <p key={index} className={`line ${line.author}`}>
            <strong>{line.author === 'entidad' ? activeName ?? 'entidad' : line.author}:</strong>{' '}
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
