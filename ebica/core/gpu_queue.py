"""
Cola de GPU con prioridades (documento base §5.14, D4; PLAN Fase 1, CP5 B2, D1-32).

Hay un solo LLM en 8 GB de VRAM: cada llamada pasa por aquí y se ejecuta de a
una, por prioridad (número menor = más urgente) y, con la misma prioridad, por
orden de llegada. Si llega un trabajo más urgente que el que está corriendo,
el que corre se **cancela** (`gpu.preempted`) y vuelve a la cola para
regenerarse desde cero (D1-32).

Detalle de implementación de D1-32: un trabajo en streaming que ya entregó
texto deja de ser interrumpible, porque lo dicho no se puede retirar. Si se
regenerara, la persona vería el texto dos veces. Antes del primer fragmento
sí se interrumpe.

En Fase 1 los turnos son seriales (un `asyncio.Lock` en el orquestador), así
que casi nunca hay dos trabajos a la vez. La interrupción se valida con
pruebas y prepara la Fase 2 (pensamientos, iniciativa y sueño).

Eventos: `gpu.enqueued`, `gpu.started` y `gpu.preempted`.
"""

import asyncio
import contextlib
import itertools
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from ebica.core.events import EventBus


class GpuPriority(IntEnum):
    """Prioridades de §5.14; las de Fase 2 (iniciativa, pensamiento, sueño) llegan con su mecanismo."""

    RESPONSE = 1
    APPRAISAL = 2
    IMPULSIVE = 3


@dataclass(eq=False)
class _Job:
    """Un trabajo para la GPU: qué ejecutar, con qué prioridad y su estado."""

    priority: GpuPriority
    sequence: int
    label: str
    entity_id: str
    cause_id: str | None
    run: Callable[["_Job"], Awaitable[Any]]
    future: asyncio.Future
    enqueued_at: float = field(default_factory=time.perf_counter)
    task: asyncio.Task | None = None
    # False en cuanto un streaming entrega su primer fragmento.
    preemptible: bool = True
    preempted: bool = False

    @property
    def order(self) -> tuple[int, int]:
        """Clave de orden: prioridad y, a igual prioridad, orden de llegada."""
        return (int(self.priority), self.sequence)


class GpuQueue:
    """Ejecuta los trabajos de LLM de a uno, por prioridad, con interrupción."""

    def __init__(self, bus: EventBus) -> None:
        """Prepara la cola vacía; los eventos se emiten en `bus`."""
        self.bus = bus
        self._pending: list[_Job] = []
        self._running: _Job | None = None
        self._sequence = itertools.count()

    @property
    def running_label(self) -> str | None:
        """Etiqueta del trabajo en curso (para pruebas y diagnóstico)."""
        return self._running.label if self._running else None

    async def run(
        self,
        priority: GpuPriority,
        label: str,
        entity_id: str,
        factory: Callable[[], Awaitable[Any]],
        cause_id: str | None = None,
    ) -> Any:
        """
        Encola un trabajo completo y espera su resultado.

        `factory` crea la corrutina cada vez que el trabajo empieza: si se
        interrumpe, se vuelve a llamar para regenerarlo desde cero.
        """
        async def execute(job: _Job) -> Any:
            """Ejecuta una vez la corrutina del trabajo."""
            return await factory()

        job = self._submit(priority, label, entity_id, cause_id, execute)
        try:
            return await asyncio.shield(job.future)
        except asyncio.CancelledError:
            self._abandon(job)
            raise

    async def stream(
        self,
        priority: GpuPriority,
        label: str,
        entity_id: str,
        factory: Callable[[], AsyncIterator[str]],
        cause_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Encola un trabajo en streaming y entrega sus fragmentos a medida que llegan.

        Mientras no haya entregado nada, puede interrumpirse y regenerarse.
        Si quien consume deja de leer, el trabajo se cancela (y el cliente LLM
        emite `llm.cancelled`).
        """
        # Tamaño 1: el trabajo no se adelanta a quien lee (contrapresión). Así,
        # si quien consume deja de leer, la generación se corta ahí mismo.
        pieces: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def execute(job: _Job) -> None:
            """Recorre el streaming y pasa cada fragmento a quien consume."""
            async with contextlib.aclosing(factory()) as generator:
                async for piece in generator:
                    job.preemptible = False
                    await pieces.put(piece)

        job = self._submit(priority, label, entity_id, cause_id, execute)
        try:
            while True:
                getter = asyncio.ensure_future(pieces.get())
                done, _ = await asyncio.wait({getter, job.future}, return_when=asyncio.FIRST_COMPLETED)
                if getter in done:
                    yield getter.result()
                    continue
                getter.cancel()
                # El trabajo terminó: entrega lo que quedó en la cola y propaga su error, si lo hubo.
                while not pieces.empty():
                    yield pieces.get_nowait()
                job.future.result()
                break
        finally:
            if not job.future.done():
                self._abandon(job)
                # Espera a que la cancelación termine, para que el cierre del
                # streaming (`llm.cancelled`) ocurra antes de devolver el control.
                if job.task is not None:
                    await asyncio.gather(job.task, return_exceptions=True)

    # ------------------------------------------------------------ interno

    def _submit(
        self,
        priority: GpuPriority,
        label: str,
        entity_id: str,
        cause_id: str | None,
        run: Callable[[_Job], Awaitable[Any]],
    ) -> _Job:
        """Crea el trabajo, lo deja en la cola y emite `gpu.enqueued`."""
        job = _Job(
            priority=priority, sequence=next(self._sequence), label=label, entity_id=entity_id,
            cause_id=cause_id, run=run, future=asyncio.get_running_loop().create_future(),
        )
        self._pending.append(job)
        self.bus.emit(
            entity_id, "gpu.enqueued",
            {"label": label, "priority": int(priority), "pending": len(self._pending),
             "running": self.running_label},
            cause_id=cause_id,
        )
        self._dispatch()
        return job

    def _dispatch(self) -> None:
        """Arranca el trabajo más urgente si la GPU está libre, o interrumpe al actual si corresponde."""
        if not self._pending:
            return
        best = min(self._pending, key=lambda j: j.order)
        running = self._running
        if running is not None:
            if best.priority < running.priority and running.preemptible and not running.preempted:
                running.preempted = True
                running.task.cancel()
            return
        self._pending.remove(best)
        self._running = best
        best.preempted = False
        best.preemptible = True
        best.task = asyncio.create_task(self._execute(best), name=f"gpu:{best.label}")
        self.bus.emit(
            best.entity_id, "gpu.started",
            {"label": best.label, "priority": int(best.priority),
             "waited_s": time.perf_counter() - best.enqueued_at},
            cause_id=best.cause_id,
        )

    async def _execute(self, job: _Job) -> None:
        """Ejecuta el trabajo y resuelve su futuro; si lo interrumpieron, lo vuelve a encolar."""
        try:
            result = await job.run(job)
        except asyncio.CancelledError:
            if job.preempted and not job.future.done():
                by = min(self._pending, key=lambda j: j.order).label if self._pending else None
                self.bus.emit(
                    job.entity_id, "gpu.preempted",
                    {"label": job.label, "priority": int(job.priority), "by": by},
                    cause_id=job.cause_id,
                )
                self._pending.append(job)
            elif not job.future.done():
                job.future.cancel()
        except Exception as error:  # el error es de quien consume: se le entrega
            if not job.future.done():
                job.future.set_exception(error)
        else:
            if not job.future.done():
                job.future.set_result(result)
        finally:
            if self._running is job:
                self._running = None
            self._dispatch()

    def _abandon(self, job: _Job) -> None:
        """Quien esperaba el trabajo ya no lo quiere: se saca de la cola o se cancela."""
        if job in self._pending:
            self._pending.remove(job)
        if not job.future.done():
            job.future.cancel()
        if job.task is not None and not job.task.done():
            job.preempted = False
            job.task.cancel()
