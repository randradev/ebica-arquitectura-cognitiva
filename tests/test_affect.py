"""
Pruebas del afecto, los drives y el bucle rápido (Fase 1, CP4).

Todas usan tiempo inyectado: el reloj falso avanza a voluntad, así que una
hora de dinámica se prueba en milisegundos y sin depender de la máquina.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from ebica.affect.drives import (
    COUPLING_WEIGHTS,
    DRIVE_THRESHOLD,
    INITIAL_DRIVES,
    DriveDynamics,
    advance_drives,
    crossed_thresholds,
    valence_coupling,
)
from ebica.affect.vad import (
    AROUSAL_HALF_LIFE_MINUTES,
    POSITIVE_VALENCE_HALF_LIFE_MINUTES,
    VAD,
    AffectDynamics,
    apply_impulse,
    decay,
)
from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import EntityConfig, EntityState
from ebica.entities.manager import Entity, EntityManager
from ebica.identity.traits import Traits, derive_parameters

CALISTO = Traits(O=0.95, C=0.30, E=0.85, A=0.40, N=0.75)
CALISTO_N_LOW = CALISTO.model_copy(update={"N": 0.25})
MINUTE = 60.0
HOUR = 3600.0


def dynamics(traits: Traits = CALISTO) -> AffectDynamics:
    """Dinámica afectiva de unos rasgos."""
    return AffectDynamics.from_parameters(derive_parameters(traits))


def time_to_half(traits: Traits, impulse: float) -> float:
    """
    Minutos que tarda la valencia en recorrer la mitad del camino al reposo
    tras un impulso, simulando con pasos de 1 s (como el bucle rápido).
    """
    affect_dynamics = dynamics(traits)
    rest = affect_dynamics.attractor
    state = apply_impulse(rest, valence=impulse)
    start_distance = abs(state.valence - rest.valence)
    seconds = 0
    while abs(state.valence - rest.valence) > start_distance / 2:
        state = decay(state, affect_dynamics, 1.0)
        seconds += 1
    return seconds / MINUTE


class FakeClock:
    """Reloj que solo avanza cuando la prueba lo pide."""

    def __init__(self) -> None:
        """Empieza en una fecha fija con zona horaria."""
        self.current = datetime(2026, 10, 25, 14, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        """Devuelve la hora actual del reloj falso."""
        return self.current

    def advance(self, seconds: float) -> None:
        """Adelanta el reloj."""
        self.current += timedelta(seconds=seconds)


def make_orchestrator(traits: Traits = CALISTO, state: EntityState | None = None):
    """Orquestador de una entidad en memoria, con reloj falso, bus y registro de guardados."""
    entity = Entity(
        config=EntityConfig(id="prueba", name="Prueba", traits=traits),
        state=state or EntityState(entity_id="prueba"),
    )
    clock, bus, saved = FakeClock(), EventBus(), []
    orchestrator = Orchestrator(entity, bus, saved.append, now=clock)
    return orchestrator, clock, bus.subscribe(), saved


def drain(queue) -> list:
    """Saca todos los eventos pendientes de una cola."""
    return [queue.get_nowait() for _ in range(queue.qsize())]


# ------------------------------------------------------------ VAD


def test_negative_valence_halves_in_h_neg():
    """Tras un golpe negativo, la valencia recorre la mitad del camino en h_neg (±2 %)."""
    assert time_to_half(CALISTO, -0.5) == pytest.approx(42.5, rel=0.02)


def test_n_variants_have_the_predicted_half_life_ratio():
    """Versión unitaria del criterio de §11: la razón de vidas medias es 42,5 / 27,5."""
    ratio = time_to_half(CALISTO, -0.5) / time_to_half(CALISTO_N_LOW, -0.5)

    assert ratio == pytest.approx(42.5 / 27.5, rel=0.02)


def test_positive_valence_uses_its_own_half_life():
    """Por encima del reposo, la valencia usa la vida media positiva (20 min, D1-15)."""
    assert time_to_half(CALISTO, +0.5) == pytest.approx(POSITIVE_VALENCE_HALF_LIFE_MINUTES, rel=0.02)


def test_closed_form_is_independent_of_step_size():
    """Un paso de una hora da lo mismo que 3600 pasos de un segundo: no se acumula error."""
    affect_dynamics = dynamics()
    start = VAD(valence=-0.6, arousal=0.9, dominance=0.1)
    one_step = decay(start, affect_dynamics, HOUR)
    many_steps = start
    for _ in range(3600):
        many_steps = decay(many_steps, affect_dynamics, 1.0)

    assert many_steps.valence == pytest.approx(one_step.valence, abs=1e-9)
    assert many_steps.arousal == pytest.approx(one_step.arousal, abs=1e-9)


def test_decay_approaches_but_never_crosses_the_attractor():
    """Tras mucho tiempo el ánimo queda en su reposo, sin pasarse al otro lado."""
    affect_dynamics = dynamics()
    rest = affect_dynamics.attractor
    state = apply_impulse(rest, valence=-0.5, arousal=0.4)

    after_an_hour = decay(state, affect_dynamics, HOUR)
    after_days = decay(state, affect_dynamics, 7 * 24 * HOUR)

    assert state.valence < after_an_hour.valence < rest.valence
    assert after_days.valence == pytest.approx(rest.valence, abs=1e-6)
    assert after_days.arousal == pytest.approx(rest.arousal, abs=1e-6)


def test_arousal_halves_in_its_half_life():
    """La alerta usa su propia vida media (10 min, D1-15)."""
    affect_dynamics = dynamics()
    rest = affect_dynamics.attractor
    start = apply_impulse(rest, arousal=0.4)

    later = decay(start, affect_dynamics, AROUSAL_HALF_LIFE_MINUTES * MINUTE)

    assert later.arousal - rest.arousal == pytest.approx((start.arousal - rest.arousal) / 2)


def test_impulses_are_clipped_to_range():
    """Un impulso enorme deja cada dimensión en su límite, no fuera de él."""
    state = apply_impulse(VAD(valence=0.5, arousal=0.5, dominance=0.5), valence=-3, arousal=3, dominance=-3)

    assert (state.valence, state.arousal, state.dominance) == (-1.0, 1.0, 0.0)


# ------------------------------------------------------------ drives


def test_drives_grow_with_time_and_respect_limits():
    """Despiertos, los drives crecen; Calisto llega al máximo de `social` en ~8,9 h y no lo supera."""
    drive_dynamics = DriveDynamics.from_parameters(derive_parameters(CALISTO))

    after_hour = advance_drives(INITIAL_DRIVES, drive_dynamics, HOUR, awake=True)
    after_day = advance_drives(INITIAL_DRIVES, drive_dynamics, 24 * HOUR, awake=True)

    assert after_hour["social"] == pytest.approx(0.2 + 1.35 / 12)
    assert after_hour["novelty"] == pytest.approx(0.2 + 1 / 24)
    assert after_hour["rest"] == pytest.approx(1 / 16)
    assert after_day == {"social": 1.0, "novelty": 1.0, "rest": 1.0}


def test_rest_recovers_while_unloaded():
    """Descargada, `rest` se recupera (vida media de 2 h) y los demás siguen creciendo."""
    drive_dynamics = DriveDynamics.from_parameters(derive_parameters(CALISTO))
    tired = {"social": 0.2, "novelty": 0.2, "rest": 0.8}

    after = advance_drives(tired, drive_dynamics, 2 * HOUR, awake=False)

    assert after["rest"] == pytest.approx(0.4)
    assert after["social"] > tired["social"]


def test_coupling_sign():
    """Que una necesidad crezca baja la valencia; que se satisfaga, la sube (Solms)."""
    low = {"social": 0.2, "novelty": 0.2, "rest": 0.2}
    high = {"social": 0.8, "novelty": 0.2, "rest": 0.2}

    assert valence_coupling(low, high) == pytest.approx(-COUPLING_WEIGHTS["social"] * 0.6)
    assert valence_coupling(high, low) == pytest.approx(+COUPLING_WEIGHTS["social"] * 0.6)


def test_threshold_crossings():
    """Se detecta el cruce del umbral al subir y al bajar, y nada si no se cruza."""
    below = {"social": DRIVE_THRESHOLD - 0.01, "novelty": 0.1, "rest": 0.1}
    above = {"social": DRIVE_THRESHOLD, "novelty": 0.1, "rest": 0.1}

    assert crossed_thresholds(below, above) == [("social", "up")]
    assert crossed_thresholds(above, below) == [("social", "down")]
    assert crossed_thresholds(below, below) == []


# ------------------------------------------------------------ orquestador


def test_wake_initializes_affect_at_rest_and_saves():
    """Una entidad nueva despierta en su reposo; se emite affect.updated y se guarda."""
    orchestrator, _, queue, saved = make_orchestrator()

    orchestrator.wake()

    assert orchestrator.state.affect == orchestrator.affect_dynamics.attractor
    events = drain(queue)
    wake = next(event for event in events if event.type == "affect.updated")
    assert wake.payload["source"] == "wake" and wake.payload["elapsed_seconds"] == 0
    assert {"drive.updated", "tick"} <= {event.type for event in events}
    assert saved


def test_injected_impulse_decays_through_ticks():
    """Un golpe manual se reporta de inmediato y, tick a tick, decae como predice h_neg."""
    orchestrator, clock, queue, _ = make_orchestrator()
    orchestrator.wake()
    rest = orchestrator.affect_dynamics.attractor.valence
    drain(queue)

    event = orchestrator.inject(valence=-0.5)
    assert event.payload["source"] == "manual"
    assert event.payload["impulse"]["valence"] == -0.5
    start = orchestrator.state.affect.valence

    for _ in range(int(42.5 * 60)):
        clock.advance(1.0)
        orchestrator.tick()

    # Los drives que crecen bajan un poco la valencia (acople), así que la
    # distancia al reposo es algo mayor que la mitad exacta.
    remaining = (orchestrator.state.affect.valence - rest) / (start - rest)
    assert remaining == pytest.approx(0.5, abs=0.06)


def test_no_affect_report_without_change():
    """En reposo y sin cambios, los ticks no emiten affect.updated antes del minuto."""
    orchestrator, clock, queue, _ = make_orchestrator()
    orchestrator.wake()
    drain(queue)

    for _ in range(30):
        clock.advance(1.0)
        orchestrator.tick()

    assert not [event for event in drain(queue) if event.type == "affect.updated"]


def test_periodic_report_and_save_every_minute():
    """Cada 60 s se reportan afecto, drives y tick, y se guarda el estado."""
    orchestrator, clock, queue, saved = make_orchestrator()
    orchestrator.wake()
    drain(queue)
    saves_before = len(saved)

    for _ in range(60):
        clock.advance(1.0)
        orchestrator.tick()

    types = [event.type for event in drain(queue)]
    assert {"affect.updated", "drive.updated", "tick"} <= set(types)
    assert len(saved) == saves_before + 1


def test_a_week_unloaded_returns_to_rest():
    """
    D1-7: tras una semana descargada, el ánimo volvió al reposo, `social` y
    `novelty` están al máximo y `rest` se recuperó.
    """
    clock = FakeClock()
    state = EntityState(
        entity_id="prueba",
        affect=VAD(valence=-0.7, arousal=0.9, dominance=0.1),
        drives={"social": 0.3, "novelty": 0.3, "rest": 0.9},
        last_tick_at=clock() - timedelta(days=7),
    )
    orchestrator, _, queue, _ = make_orchestrator(state=state)
    orchestrator.now = clock

    orchestrator.wake()

    rest = orchestrator.affect_dynamics.attractor
    assert orchestrator.state.affect.valence == pytest.approx(rest.valence, abs=1e-3)
    assert orchestrator.state.affect.arousal == pytest.approx(rest.arousal, abs=1e-3)
    assert orchestrator.state.drives["social"] == 1.0
    assert orchestrator.state.drives["novelty"] == 1.0
    assert orchestrator.state.drives["rest"] == pytest.approx(0.0, abs=1e-6)
    events = drain(queue)
    wake = next(event for event in events if event.type == "affect.updated")
    assert wake.payload["elapsed_seconds"] == pytest.approx(7 * 24 * HOUR)
    crossings = [event.payload for event in events if event.type == "drive.threshold_crossed"]
    assert {(c["drive"], c["direction"]) for c in crossings} == {
        ("rest", "down"), ("social", "up"), ("novelty", "up"),
    }
    assert all(c["awake"] is False for c in crossings)


def test_state_survives_save_and_load(tmp_path):
    """El ánimo, los drives y el último tick se guardan en state.json y se recuperan al cargar."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    manager.create(EntityConfig(id="prueba", name="Prueba", traits=CALISTO))
    entity = manager.load("prueba")
    clock = FakeClock()
    orchestrator = Orchestrator(entity, bus, manager.save_state, now=clock)
    orchestrator.wake()
    orchestrator.inject(valence=-0.4, arousal=0.3)
    manager.save_state(entity.state)

    reloaded = manager.load("prueba")

    assert reloaded.state.affect == entity.state.affect
    assert reloaded.state.drives == entity.state.drives
    assert reloaded.state.last_tick_at == clock()


async def test_fast_loop_runs_as_a_task_and_stops_cleanly():
    """start() lanza el bucle; stop() lo detiene, hace el último tick y guarda."""
    orchestrator, clock, _, saved = make_orchestrator()
    orchestrator.tick_seconds = 0.01

    orchestrator.start()
    await asyncio.sleep(0.1)
    ticks_while_running = orchestrator._ticks
    await orchestrator.stop()

    assert ticks_while_running >= 3
    assert orchestrator._task is None
    assert saved
