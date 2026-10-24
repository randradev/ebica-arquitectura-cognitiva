import { useState } from 'react'
import { Chat } from './Chat'
import { EntityPanel } from './EntityPanel'
import { EventLog } from './EventLog'
import { useEvents } from './useEvents'

/**
 * Consola mínima de Fase 0 (§8.3): a la izquierda la entidad y el chat; a la
 * derecha, todo lo que ocurre dentro del motor, en vivo.
 */
export default function App() {
  const [activeId, setActiveId] = useState<string | null>(null)
  const { events, connected } = useEvents()

  return (
    <main className="layout">
      <div className="left">
        <h1>EBICA</h1>
        <EntityPanel onActive={setActiveId} />
        <Chat activeId={activeId} />
      </div>
      <div className="right">
        <EventLog events={events} connected={connected} />
      </div>
    </main>
  )
}
