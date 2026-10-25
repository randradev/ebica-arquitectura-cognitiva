import { useCallback, useState } from 'react'
import { AffectPanel } from './AffectPanel'
import { Chat } from './Chat'
import { EntityPanel } from './EntityPanel'
import { EventLog } from './EventLog'
import { TurnPanel } from './TurnPanel'
import { useEvents } from './useEvents'

/**
 * Consola (§8.3): a la izquierda la entidad, su ánimo y el chat; a la
 * derecha, todo lo que ocurre dentro del motor, en vivo.
 */
export default function App() {
  const [active, setActive] = useState<{ id: string; name: string } | null>(null)
  const { events, connected } = useEvents()
  const onActive = useCallback(
    (id: string | null, name: string | null) => setActive(id ? { id, name: name ?? id } : null),
    [],
  )

  return (
    <main className="layout">
      <div className="left">
        <h1>EBICA</h1>
        <EntityPanel onActive={onActive} />
        <AffectPanel events={events} activeId={active?.id ?? null} />
        <Chat activeId={active?.id ?? null} activeName={active?.name ?? null} />
      </div>
      <div className="right">
        <TurnPanel events={events} activeId={active?.id ?? null} />
        <EventLog events={events} connected={connected} />
      </div>
    </main>
  )
}
