"""
Pruebas de la cola de GPU (Fase 1, CP5 parte B2; §5.14, D1-32), con trabajos simulados.

Cubren el orden por prioridad y llegada, la interrupción con regeneración, que
un streaming que ya habló no se interrumpe, la propagación de errores y el
abandono por parte de quien espera.
"""

import asyncio

import pytest
from fake_llm import drain

from ebica.core.events import EventBus
from ebica.core.gpu_queue import GpuPriority, GpuQueue

ENTITY = "prueba"


def make_queue() -> tuple[GpuQueue, asyncio.Queue]:
    """Una cola con su bus y un suscriptor para revisar los eventos."""
    bus = EventBus()
    return GpuQueue(bus), bus.subscribe()


async def test_jobs_run_one_at_a_time_by_priority_then_arrival():
    """Con la GPU ocupada, lo pendiente sale por prioridad y, a igual prioridad, por llegada."""
    queue, _ = make_queue()
    gate = asyncio.Event()
    order: list[str] = []

    async def job(name: str, wait: bool = False) -> str:
        """Registra cuándo corre; el primero espera la señal para dejar la GPU ocupada."""
        order.append(name)
        if wait:
            await gate.wait()
        return name

    blocker = asyncio.create_task(queue.run(GpuPriority.RESPONSE, "ocupa", ENTITY, lambda: job("ocupa", True)))
    await asyncio.sleep(0)
    tasks = [
        asyncio.create_task(queue.run(GpuPriority.IMPULSIVE, "imp", ENTITY, lambda: job("imp"))),
        asyncio.create_task(queue.run(GpuPriority.APPRAISAL, "app1", ENTITY, lambda: job("app1"))),
        asyncio.create_task(queue.run(GpuPriority.APPRAISAL, "app2", ENTITY, lambda: job("app2"))),
    ]
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(blocker, *tasks)

    assert order == ["ocupa", "app1", "app2", "imp"]


async def test_higher_priority_preempts_and_the_preempted_job_regenerates():
    """Un trabajo más urgente cancela al que corre (`gpu.preempted`); el cancelado se rehace desde cero."""
    queue, events = make_queue()
    started = asyncio.Event()
    attempts = 0

    async def slow_impulsive() -> str:
        """Tarda; la primera vez será interrumpido."""
        nonlocal attempts
        attempts += 1
        started.set()
        await asyncio.sleep(0.05)
        return f"impulsiva (intento {attempts})"

    async def appraisal() -> str:
        """Trabajo urgente y rápido."""
        return "appraisal"

    low = asyncio.create_task(queue.run(GpuPriority.IMPULSIVE, "imp", ENTITY, slow_impulsive))
    await started.wait()
    high = await queue.run(GpuPriority.APPRAISAL, "app", ENTITY, appraisal)

    assert high == "appraisal"
    assert await low == "impulsiva (intento 2)"
    preempted = [e for e in drain(events) if e.type == "gpu.preempted"]
    assert len(preempted) == 1 and preempted[0].payload == {"label": "imp", "priority": 3, "by": "app"}


async def test_equal_priority_does_not_preempt():
    """A igual prioridad se espera el turno: no hay interrupción."""
    queue, events = make_queue()
    started = asyncio.Event()

    async def first() -> str:
        """Ocupa la GPU un momento."""
        started.set()
        await asyncio.sleep(0.02)
        return "primero"

    async def second() -> str:
        """Llega después con la misma prioridad."""
        return "segundo"

    one = asyncio.create_task(queue.run(GpuPriority.APPRAISAL, "a", ENTITY, first))
    await started.wait()
    assert await queue.run(GpuPriority.APPRAISAL, "b", ENTITY, second) == "segundo"
    assert await one == "primero"
    assert not [e for e in drain(events) if e.type == "gpu.preempted"]


async def test_stream_that_already_spoke_is_not_preempted():
    """Lo dicho no se retira: tras el primer fragmento, el streaming termina aunque llegue algo urgente."""
    queue, events = make_queue()
    spoke = asyncio.Event()

    async def speech():
        """Un streaming lento de tres fragmentos."""
        yield "uno"
        spoke.set()
        await asyncio.sleep(0.02)
        yield "dos"
        yield "tres"

    async def urgent() -> str:
        """Llega mientras el streaming habla."""
        return "urgente"

    async def consume() -> list[str]:
        """Lee todo el streaming."""
        return [p async for p in queue.stream(GpuPriority.IMPULSIVE, "imp", ENTITY, speech)]

    reader = asyncio.create_task(consume())
    await spoke.wait()
    assert await queue.run(GpuPriority.RESPONSE, "resp", ENTITY, urgent) == "urgente"
    assert await reader == ["uno", "dos", "tres"]
    assert not [e for e in drain(events) if e.type == "gpu.preempted"]


async def test_stream_preempted_before_speaking_regenerates():
    """Antes del primer fragmento, un streaming sí se interrumpe y se rehace."""
    queue, events = make_queue()
    thinking = asyncio.Event()
    attempts = 0

    async def speech():
        """La primera vez tarda en empezar; la segunda habla de inmediato."""
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            thinking.set()
            await asyncio.sleep(1)
        yield f"intento {attempts}"

    async def urgent() -> str:
        """Trabajo urgente."""
        return "ok"

    async def consume() -> list[str]:
        """Lee todo el streaming."""
        return [p async for p in queue.stream(GpuPriority.IMPULSIVE, "imp", ENTITY, speech)]

    reader = asyncio.create_task(consume())
    await thinking.wait()
    await queue.run(GpuPriority.APPRAISAL, "app", ENTITY, urgent)

    assert await reader == ["intento 2"]
    assert [e.type for e in drain(events)].count("gpu.preempted") == 1


async def test_errors_reach_the_caller_and_the_queue_keeps_working():
    """El error de un trabajo llega a quien lo pidió; la cola sigue atendiendo."""
    queue, _ = make_queue()

    async def broken() -> None:
        """Falla como un servidor caído."""
        raise RuntimeError("servidor caído")

    async def fine() -> str:
        """Trabajo normal."""
        return "ok"

    with pytest.raises(RuntimeError, match="servidor caído"):
        await queue.run(GpuPriority.APPRAISAL, "roto", ENTITY, broken)
    assert await queue.run(GpuPriority.APPRAISAL, "bien", ENTITY, fine) == "ok"
    assert queue.running_label is None


async def test_abandoned_pending_job_never_runs():
    """Si quien espera se va antes de que empiece, el trabajo sale de la cola sin ejecutarse."""
    queue, _ = make_queue()
    gate = asyncio.Event()
    ran: list[str] = []

    async def blocker() -> None:
        """Ocupa la GPU hasta la señal."""
        await gate.wait()

    async def never() -> None:
        """No debería ejecutarse."""
        ran.append("never")

    busy = asyncio.create_task(queue.run(GpuPriority.RESPONSE, "ocupa", ENTITY, blocker))
    await asyncio.sleep(0)
    waiting = asyncio.create_task(queue.run(GpuPriority.APPRAISAL, "espera", ENTITY, never))
    await asyncio.sleep(0)
    waiting.cancel()
    gate.set()
    await busy
    await asyncio.sleep(0)

    assert ran == []


async def test_events_are_emitted_with_cause():
    """`gpu.enqueued` y `gpu.started` llevan etiqueta, prioridad y el `cause_id` del trabajo."""
    queue, events = make_queue()

    async def job() -> str:
        """Trabajo trivial."""
        return "ok"

    await queue.run(GpuPriority.APPRAISAL, "appraisal", ENTITY, job, cause_id="evt-1")
    by_type = {e.type: e for e in drain(events)}

    assert by_type["gpu.enqueued"].payload["label"] == "appraisal"
    assert by_type["gpu.started"].payload["priority"] == 2
    assert by_type["gpu.started"].cause_id == "evt-1"
