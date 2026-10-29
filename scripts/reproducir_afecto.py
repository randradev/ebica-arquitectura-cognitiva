"""
Reproducción de la trayectoria afectiva sin el LLM (CP10b parte A).

Lee el JSONL de eventos de una conversación real y vuelve a vivirla con el motor
actual: parte del ánimo y los drives del último `wake`, avanza el reloj segundo a
segundo como el bucle rápido (§6.1) y, en cada turno, aplica el mismo appraisal
que se registró (ya corregido por las reglas de coherencia) con
`Orchestrator.apply_appraisal`. También reproduce la alarma de la vía baja, los
impulsos manuales y la novedad de `repetition_watch`.

Con el motor sin cambios debe dar lo mismo que lo registrado (esa es su prueba).
Con fórmulas nuevas (CP10b B) muestra cómo se habría movido el ánimo ante los
mismos mensajes, sin el ruido del LLM. No imprime el texto de las conversaciones,
salvo con `--textos`.

Uso, desde la raíz del repositorio:
    .venv/Scripts/python.exe scripts/reproducir_afecto.py <eventos.jsonl> [--config calisto] [--textos] [--json salida.json]
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ebica.affect.appraisal_effects as appraisal_effects  # noqa: E402
import ebica.affect.vad as vad  # noqa: E402
from ebica.affect.low_road import ALARM_AROUSAL  # noqa: E402
from ebica.affect.vad import VAD  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.core.orchestrator import Orchestrator  # noqa: E402
from ebica.core.state import EntityState  # noqa: E402
from ebica.entities.manager import Entity, EntityManager  # noqa: E402
from ebica.perception.appraisal import Appraisal  # noqa: E402

# CONSTANTES: criterios de D1-82 (fijados antes de medir).
SATURATED = 0.99          # |valencia| o alerta desde la que se cuenta «en el tope»
NEUTRAL_PARTNER = 0.2     # |valencia ajena| bajo la que un mensaje se considera neutro
REBOUND = 0.15            # subida de la valencia que, ante un mensaje neutro, es un rebote
STEP = timedelta(seconds=1)


@dataclass
class TurnReplay:
    """Un turno reproducido: lo registrado frente a lo recalculado."""

    index: int
    text: str
    person: str | None
    impulsive: bool
    partner_valence: float
    recorded: VAD | None
    replayed: VAD
    before: VAD
    flags: list[str] = field(default_factory=list)

    @property
    def delta_valence(self) -> float:
        """Cuánto movió la valencia el turno, en la reproducción."""
        return self.replayed.valence - self.before.valence

    def as_dict(self, texts: bool = False) -> dict:
        """Versión JSON (el texto solo si se pide)."""
        data = {
            "turno": self.index, "persona": self.person, "impulsivo": self.impulsive,
            "valencia_ajena": round(self.partner_valence, 3),
            "registrado": self.recorded.model_dump() if self.recorded else None,
            "reproducido": self.replayed.model_dump(), "delta_valencia": round(self.delta_valence, 3),
            "marcas": self.flags,
        }
        return data | ({"texto": self.text} if texts else {})


def _ts(event: dict) -> datetime:
    """La hora de un evento."""
    return datetime.fromisoformat(event["ts"])


def replay(events: list[dict], config_id: str, step: timedelta | None = STEP) -> list[TurnReplay]:
    """
    Vuelve a vivir los eventos con el motor actual y devuelve un registro por turno.

    `step` es el paso del reloj entre eventos: 1 s reproduce el bucle rápido del
    servidor; `None` salta directo de un evento al siguiente (como un
    orquestador sin el bucle corriendo, en las pruebas). El acople drive →
    valencia acumula distinto según el paso, así que debe coincidir con el original.
    """
    config = EntityManager(ROOT / "entities", EventBus()).read_config(config_id)
    clock = [_ts(events[0])]
    entity = Entity(config=config, state=EntityState(entity_id=config.id))
    orchestrator = Orchestrator(entity, EventBus(), lambda state: None, now=lambda: clock[0])
    turn_payloads = [e["payload"] for e in events if e["type"] == "turn.completed"]
    texts = [e["payload"]["text"] for e in events if e["type"] == "perception.input"]
    results: list[TurnReplay] = []
    turn_index = 0
    pending_wake = False

    def advance_to(moment: datetime) -> None:
        """Avanza el reloj segundo a segundo hasta `moment`, como el bucle rápido."""
        while step is not None and clock[0] + step <= moment:
            clock[0] += step
            orchestrator.tick()
        clock[0] = moment

    for event in events:
        kind, payload = event["type"], event["payload"]
        if kind == "affect.updated" and payload["source"] == "wake":
            clock[0] = _ts(event)
            entity.state.affect = VAD(valence=payload["valence"], arousal=payload["arousal"],
                                      dominance=payload["dominance"])
            entity.state.last_tick_at = clock[0]
            pending_wake = True
            continue
        if kind == "drive.updated" and pending_wake:
            entity.state.drives = dict(payload)
            pending_wake = False
            continue
        if entity.state.affect is None:
            continue
        if kind == "affect.updated" and payload["source"] == "manual":
            advance_to(_ts(event))
            orchestrator.inject(**payload["impulse"])
        elif kind == "affect.updated" and payload["source"] == "low_road":
            advance_to(_ts(event))
            orchestrator.tick()
            entity.state.affect = vad.apply_soft_impulse(entity.state.affect, arousal=ALARM_AROUSAL)
        elif kind == "agent.signal" and payload["kind"] == "user_repeats":
            advance_to(_ts(event))
            orchestrator._raise_novelty(payload["data"]["novelty"], event["id"])
        elif kind == "appraisal.completed" and turn_index < len(turn_payloads):
            advance_to(_ts(event))
            turn = turn_payloads[turn_index]
            model = ((turn.get("partner") or {}).get("model")) or {}
            scale = 1.0 if not model or model.get("primary") else model.get("trust", 1.0)
            trust = model.get("trust", 1.0) if model else 1.0
            before = entity.state.affect
            appraisal = Appraisal.model_validate(payload["appraisal"])
            orchestrator.apply_appraisal(
                appraisal, payload["corrections"], alarm_arousal=ALARM_AROUSAL if turn["impulsive"] else 0.0,
                social_scale=scale, trust=trust,
            )
            after = turn["affect_after"]
            results.append(TurnReplay(
                index=turn_index + 1, text=texts[turn_index] if turn_index < len(texts) else "",
                person=(turn.get("partner") or {}).get("person_id"), impulsive=turn["impulsive"],
                partner_valence=appraisal.user_emotion.valence,
                recorded=VAD(valence=after["valence"], arousal=after["arousal"], dominance=after["dominance"]),
                replayed=entity.state.affect, before=before,
            ))
            turn_index += 1
    for turn in results:
        if abs(turn.replayed.valence) >= SATURATED:
            turn.flags.append("tope de valencia")
        if turn.replayed.arousal >= SATURATED:
            turn.flags.append("tope de alerta")
        if abs(turn.partner_valence) < NEUTRAL_PARTNER and turn.delta_valence > REBOUND:
            turn.flags.append("rebote")
    return results


def summary(turns: list[TurnReplay]) -> dict:
    """Las métricas de D1-82 de una reproducción."""
    return {
        "turnos": len(turns),
        "tope_valencia": sum("tope de valencia" in t.flags for t in turns),
        "tope_alerta": sum("tope de alerta" in t.flags for t in turns),
        "rebotes": sum("rebote" in t.flags for t in turns),
        "mayor_salto": round(max((abs(t.delta_valence) for t in turns), default=0.0), 3),
        "max_diferencia_con_lo_registrado": round(max(
            (max(abs(t.replayed.valence - t.recorded.valence), abs(t.replayed.arousal - t.recorded.arousal),
                 abs(t.replayed.dominance - t.recorded.dominance)) for t in turns if t.recorded),
            default=0.0), 4),
    }


def set_engine(soft_saturation: bool = True, dead_zone: bool = True, trust: bool = True) -> None:
    """
    Enciende o apaga los cambios de CP10b en el motor (D1-79, D1-80), para
    medir cada uno por separado. Todo apagado = el motor de CP10.
    """
    vad.SOFT_SATURATION = soft_saturation
    appraisal_effects.EMPATHY_DEAD_ZONE = 0.2 if dead_zone else 0.0
    appraisal_effects.EMPATHY_TRUST_BASE = 0.5 if trust else 1.0


def main() -> None:
    """Reproduce un JSONL e imprime la trayectoria y el resumen."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--motor-cp10", action="store_true", help="apaga los tres cambios de CP10b")
    parser.add_argument("--sin-saturacion-suave", action="store_true")
    parser.add_argument("--sin-zona-muerta", action="store_true")
    parser.add_argument("--sin-confianza", action="store_true")
    parser.add_argument("eventos", type=Path)
    parser.add_argument("--config", default="calisto")
    parser.add_argument("--textos", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    set_engine(
        soft_saturation=not (args.motor_cp10 or args.sin_saturacion_suave),
        dead_zone=not (args.motor_cp10 or args.sin_zona_muerta),
        trust=not (args.motor_cp10 or args.sin_confianza),
    )
    events = [json.loads(line) for line in args.eventos.read_text(encoding="utf-8").splitlines() if line.strip()]
    turns = replay(events, args.config)
    for t in turns:
        recorded = f"{t.recorded.valence:+.2f}" if t.recorded else "—"
        label = f" «{t.text[:50]}»" if args.textos else ""
        print(f"#{t.index:2} [{t.person or '-'}]{label} ajena {t.partner_valence:+.2f} · v {t.before.valence:+.2f} → "
              f"{t.replayed.valence:+.2f} (registrado {recorded}) · a {t.replayed.arousal:.2f} · {', '.join(t.flags)}")
    result = summary(turns)
    print(json.dumps(result, ensure_ascii=False))
    if args.json:
        args.json.write_text(json.dumps({"resumen": result, "turnos": [t.as_dict(args.textos) for t in turns]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
