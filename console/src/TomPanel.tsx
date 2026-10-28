import type { EngineEvent, PersonSummary } from './types'

interface PartnerNow {
  valence: number
  arousal: number
  intent: string
  topics: string[]
  distress: number
  hostility: number
}

/** Número con signo y dos decimales (p. ej. "+0.12", "−0.42"). */
function signed(value: number): string {
  return `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(2)}`
}

/**
 * Panel de Teoría de la Mente (§8.3, §5.9; CP8): a quién cree la entidad que
 * le habla y qué sabe de esa persona. `partner_now` es cómo la percibió en el
 * último mensaje (del appraisal); el modelo, lo acumulado en el `Person`.
 * Se arma con el último `tom.updated` o `tom.partner_switched` de la entidad.
 */
export function TomPanel({ events, activeId }: { events: EngineEvent[]; activeId: string | null }) {
  const event = events.find(
    (item) => item.entity_id === activeId && (item.type === 'tom.updated' || item.type === 'tom.partner_switched'),
  )
  if (!activeId || !event) return null
  const payload = event.payload as { model?: PersonSummary; person?: PersonSummary; now?: PartnerNow }
  const model = payload.model ?? payload.person
  if (!model) return null
  // Tras un cambio de persona todavía no hay percepción de este interlocutor.
  const now = event.type === 'tom.updated' ? payload.now : undefined

  return (
    <section className="turn-panel">
      <h2>
        Teoría de la Mente · {model.name}
        {model.primary && <span className="muted"> (principal)</span>}
      </h2>
      <div className="turn-grid">
        <div>
          <h3>Ahora (último mensaje)</h3>
          {now ? (
            <>
              <p>
                valencia {signed(now.valence)} · alerta {now.arousal.toFixed(2)} · angustia {now.distress.toFixed(2)} ·
                hostilidad {now.hostility.toFixed(2)}
              </p>
              <p className="muted">
                busca: {now.intent || '—'} · foco: {now.topics.join(', ') || '—'}
              </p>
            </>
          ) : (
            <p className="muted">sin mensajes de esta persona todavía</p>
          )}
        </div>
        <div>
          <h3>Modelo</h3>
          <p>
            {model.n} intercambios · confianza {model.trust.toFixed(2)} · valencia media {signed(model.valence_mean)} ·
            alerta media {model.arousal_mean.toFixed(2)}
          </p>
          <p className="muted">temas: {model.top_topics.join(', ') || '—'}</p>
          <p className="muted">sensibles: {model.top_sensitive.join(', ') || '—'}</p>
          <p className="muted">
            primer intercambio: {model.first_met ? new Date(model.first_met).toLocaleString() : '—'}
          </p>
        </div>
      </div>
    </section>
  )
}
