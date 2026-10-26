import type { EngineEvent } from './types'

interface LowRoadRule {
  rule: string
  signal: number
  evidence: string
}

interface TurnPayload {
  impulsive: boolean
  low_road: { score: number; threshold: number; triggered: boolean; rules: LowRoadRule[] }
  appraisal: {
    user_emotion: { valence: number; arousal: number; dominance: number }
    user_intent: string
    topics: string[]
    hostility: number
    distress: number
    self_relevance: number
    goal_congruence: number
    novelty: number
  }
  corrections: string[]
  affect_after: {
    valence: number
    arousal: number
    dominance: number
    impulse?: { valence_from_goals: number; valence_from_empathy: number; arousal: number; dominance: number }
    drive_relief?: Record<string, number>
    valence_from_drives?: number
    alarm_arousal_discounted?: number
  }
  // null en un turno impulsivo: el preset `impulsive` usa su temperatura fija.
  temperature: number | null
  latency: {
    low_road_ms: number
    appraisal_s: number
    first_token_s: number | null
    response_s: number | null
    total_s: number
  }
}

/** Número con signo y dos decimales (p. ej. "+0.12", "−0.42"). */
function signed(value: number | undefined): string {
  if (value === undefined) return '—'
  return `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(2)}`
}

/** Segundos con un decimal, o "—" si no se midió. */
function seconds(value: number | null | undefined): string {
  return value == null ? '—' : `${value.toFixed(1)} s`
}

/**
 * Panel «último turno» (§8.3): la vía baja (puntaje, umbral y reglas), qué
 * evaluó el appraisal del último mensaje, qué impulsos produjo, la
 * temperatura de la respuesta y las latencias. Un turno impulsivo se marca:
 * ahí la respuesta salió antes del appraisal.
 * Se arma con el evento `turn.completed` más reciente de la entidad activa.
 */
export function TurnPanel({ events, activeId }: { events: EngineEvent[]; activeId: string | null }) {
  const event = events.find((item) => item.type === 'turn.completed' && item.entity_id === activeId)
  if (!activeId || !event) return null
  const turn = event.payload as unknown as TurnPayload
  const a = turn.appraisal
  const effect = turn.affect_after

  return (
    <section className="turn-panel">
      <h2>Último turno{turn.impulsive && <span className="warning"> · impulsivo</span>}</h2>
      <div className="turn-grid">
        <div>
          <h3>Vía baja</h3>
          <p>
            puntaje {turn.low_road.score.toFixed(2)} · umbral {turn.low_road.threshold.toFixed(3)} ·{' '}
            {turn.low_road.triggered ? <span className="warning">disparada</span> : 'no disparada'}
          </p>
          {turn.low_road.rules.map((rule) => (
            <p key={rule.rule} className="muted">
              {rule.rule} {rule.signal.toFixed(2)} · «{rule.evidence}»
            </p>
          ))}
        </div>
        <div>
          <h3>Appraisal{turn.impulsive && ' (después de responder)'}</h3>
          <p>
            hostilidad {a.hostility.toFixed(2)} · angustia {a.distress.toFixed(2)} · valencia ajena{' '}
            {signed(a.user_emotion.valence)}
          </p>
          <p>
            metas {signed(a.goal_congruence)} · autorrelevancia {a.self_relevance.toFixed(2)} · novedad{' '}
            {a.novelty.toFixed(2)}
          </p>
          <p className="muted">
            intención: {a.user_intent || '—'} · temas: {a.topics.join(', ') || '—'}
          </p>
          {turn.corrections.length > 0 && <p className="warning">{turn.corrections.join(' · ')}</p>}
        </div>
        <div>
          <h3>Impulsos</h3>
          <p>
            valencia: metas {signed(effect.impulse?.valence_from_goals)} · empatía{' '}
            {signed(effect.impulse?.valence_from_empathy)} · drives {signed(effect.valence_from_drives)}
          </p>
          <p>
            alerta {signed(effect.impulse?.arousal)} · dominancia {signed(effect.impulse?.dominance)}
          </p>
          {effect.alarm_arousal_discounted ? (
            <p className="muted">alarma de la vía baja: alerta +{effect.alarm_arousal_discounted.toFixed(2)} (ya descontada)</p>
          ) : null}
          <p className="muted">
            alivio: social {effect.drive_relief?.social.toFixed(2) ?? '—'} · novedad{' '}
            {effect.drive_relief?.novelty.toFixed(2) ?? '—'}
          </p>
        </div>
        <div>
          <h3>Respuesta</h3>
          <p>{turn.temperature === null ? 'preset impulsive (0.50)' : `temperatura ${turn.temperature.toFixed(2)}`}</p>
          <p>
            appraisal {seconds(turn.latency.appraisal_s)} · primer token {seconds(turn.latency.first_token_s)}
          </p>
          <p className="muted">
            vía baja {(turn.latency.low_road_ms ?? 0).toFixed(1)} ms · turno completo {seconds(turn.latency.total_s)}
          </p>
        </div>
      </div>
    </section>
  )
}
