import { useState } from 'react'
import type { EngineEvent } from './types'

// CONSTANTE: umbral de los drives (D1-16); se marca sobre cada barra.
const DRIVE_THRESHOLD = 0.7

// Impulsos de laboratorio (D1-18). Quedan registrados con `source: "manual"`.
const IMPULSES: { label: string; body: Record<string, number> }[] = [
  { label: 'valencia −0,5', body: { valence: -0.5 } },
  { label: 'valencia +0,5', body: { valence: 0.5 } },
  { label: 'alerta +0,3', body: { arousal: 0.3 } },
  { label: 'dominancia −0,3', body: { dominance: -0.3 } },
]

interface Vad {
  valence: number
  arousal: number
  dominance: number
}

/** El evento más reciente de un tipo para la entidad activa (la lista viene del más nuevo al más viejo). */
function latest(events: EngineEvent[], type: string, entityId: string): EngineEvent | undefined {
  return events.find((event) => event.type === type && event.entity_id === entityId)
}

/**
 * Una barra horizontal con el valor actual y una marca opcional (reposo o umbral).
 * `min`/`max` permiten la escala −1..1 de la valencia.
 */
function Bar({ label, value, mark, min = 0, max = 1 }: {
  label: string; value: number; mark?: number; min?: number; max?: number
}) {
  const percent = (x: number) => ((x - min) / (max - min)) * 100
  // La barra crece desde 0: en la valencia, hacia la izquierda si es negativa.
  const zero = percent(Math.max(min, 0))
  const left = Math.min(zero, percent(value))
  const width = Math.abs(percent(value) - zero)
  return (
    <div className="bar">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div className={`bar-fill ${value < 0 ? 'negative' : ''}`} style={{ left: `${left}%`, width: `${width}%` }} />
        {mark !== undefined && <div className="bar-mark" style={{ left: `${percent(mark)}%` }} />}
      </div>
      <span className="bar-value">{value.toFixed(2)}</span>
    </div>
  )
}

/**
 * Ánimo (VAD) y drives de la entidad activa, en vivo (§8.3). Se arma con los
 * eventos `affect.updated` y `drive.updated`; la marca blanca es el reposo
 * del VAD o el umbral de los drives. Incluye los botones para inyectar afecto.
 */
export function AffectPanel({ events, activeId }: { events: EngineEvent[]; activeId: string | null }) {
  const [error, setError] = useState<string | null>(null)
  if (!activeId) return null

  const affectEvent = latest(events, 'affect.updated', activeId)
  const drivesEvent = latest(events, 'drive.updated', activeId)
  const affect = affectEvent?.payload as (Vad & { attractor: Vad; source: string }) | undefined
  const drives = drivesEvent?.payload as Record<string, number> | undefined

  /** Envía un impulso manual al VAD de la entidad activa. */
  async function inject(body: Record<string, number>): Promise<void> {
    setError(null)
    const response = await fetch('/api/affect/impulse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) setError((await response.json()).detail ?? `Error ${response.status}`)
  }

  return (
    <section className="affect-panel">
      {affect ? (
        <>
          <Bar label="valencia" value={affect.valence} mark={affect.attractor.valence} min={-1} />
          <Bar label="alerta" value={affect.arousal} mark={affect.attractor.arousal} />
          <Bar label="dominancia" value={affect.dominance} mark={affect.attractor.dominance} />
          <p className="muted">
            Último reporte: {new Date(affectEvent!.ts).toLocaleTimeString()} ({affect.source})
          </p>
        </>
      ) : (
        <p className="muted">Sin datos de afecto todavía.</p>
      )}
      {drives &&
        Object.entries(drives).map(([name, level]) => (
          <Bar key={name} label={name} value={level} mark={DRIVE_THRESHOLD} />
        ))}
      <div className="row impulses">
        {IMPULSES.map((impulse) => (
          <button key={impulse.label} onClick={() => inject(impulse.body)} title="Estímulo de laboratorio (D1-18)">
            {impulse.label}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
