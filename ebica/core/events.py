"""
Eventos estructurados del motor (decisión D10 del documento base, §8.2).

Todo componente informa lo que hace emitiendo un `Event`. El `EventBus` los
reparte a quien escuche (por ejemplo, la consola) y los guarda en un archivo
JSONL por día, para poder reproducir una sesión y calcular métricas después.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# CONSTANTE: formato válido de un `entity_id`.
# El id se usa como nombre de carpeta en disco; restringirlo a minúsculas,
# dígitos, "_" y "-" evita rutas peligrosas (por ejemplo, "../otra_carpeta").
ENTITY_ID_PATTERN = r"^[a-z0-9_-]+$"

# CONSTANTE: formato válido del tipo de evento: "familia.nombre" (p. ej.
# "entity.loaded") o una sola palabra (p. ej. "tick"), como en la tabla §8.2.
EVENT_TYPE_PATTERN = r"^[a-z_]+(\.[a-z_]+)*$"


def _utc_now() -> datetime:
    """Devuelve la hora actual con zona horaria UTC."""
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    """Genera un identificador único para un evento."""
    return uuid.uuid4().hex


class Event(BaseModel):
    """
    Un hecho ocurrido dentro del motor.

    `cause_id` apunta al `id` del evento que lo provocó; así se puede seguir
    la cadena causa → efecto (p. ej. `perception.input` → `llm.request`).
    """

    id: str = Field(default_factory=_new_event_id)
    ts: datetime = Field(default_factory=_utc_now)
    entity_id: str = Field(pattern=ENTITY_ID_PATTERN)
    type: str = Field(pattern=EVENT_TYPE_PATTERN)
    payload: dict[str, Any] = Field(default_factory=dict)
    cause_id: str | None = None


class JsonlEventLog:
    """
    Persistencia de eventos: un archivo JSONL por entidad y por día.

    Ruta: `<base_dir>/<entity_id>/events/AAAA-MM-DD.jsonl`, una línea JSON por evento.
    """

    def __init__(self, base_dir: Path) -> None:
        """Guarda la carpeta raíz de las entidades (normalmente `entities/`)."""
        self.base_dir = Path(base_dir)

    def path_for(self, entity_id: str, day: datetime) -> Path:
        """
        Devuelve la ruta del archivo del día para una entidad.

        El día se calcula en UTC para que un mismo evento caiga siempre en el
        mismo archivo, sin depender de la zona horaria ni del cambio de hora.
        """
        day_utc = day.astimezone(timezone.utc).date()
        return self.base_dir / entity_id / "events" / f"{day_utc.isoformat()}.jsonl"

    def append(self, event: Event) -> None:
        """
        Añade un evento al final del archivo de su día.

        Efecto secundario: crea las carpetas si no existen. La escritura es
        síncrona; con eventos pequeños es suficientemente rápida para Fase 0.
        """
        path = self.path_for(event.entity_id, event.ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(event.model_dump_json() + "\n")

    def read(self, entity_id: str, day: datetime) -> list[Event]:
        """Lee y reconstruye todos los eventos de un día; lista vacía si no hay archivo."""
        path = self.path_for(entity_id, day)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as file:
            return [Event.model_validate_json(line) for line in file if line.strip()]


class EventBus:
    """
    Reparte cada evento a los suscriptores y lo persiste.

    Cada suscriptor recibe su propia `asyncio.Queue`: emitir nunca espera a
    que un suscriptor lento (p. ej. una consola) termine de leer.
    """

    def __init__(self, log: JsonlEventLog | None = None) -> None:
        """Crea el bus; si `log` es None, los eventos no se guardan en disco."""
        self.log = log
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def subscribe(self) -> asyncio.Queue[Event]:
        """
        Registra un nuevo suscriptor y devuelve la cola donde recibirá eventos.

        Las colas no tienen límite de tamaño; si una consola deja de leer,
        su cola crece. Se revisará cuando haya consumidores reales (CP5).
        """
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Deja de enviar eventos a esa cola (no falla si ya no estaba registrada)."""
        self._subscribers.discard(queue)

    def publish(self, event: Event) -> Event:
        """
        Persiste un evento ya construido y lo entrega a todos los suscriptores.

        Primero se guarda en disco: el registro es la fuente de verdad para
        reproducir sesiones, aunque nadie esté mirando la consola.
        """
        if self.log is not None:
            self.log.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def emit(
        self,
        entity_id: str,
        type: str,
        payload: dict[str, Any] | None = None,
        cause_id: str | None = None,
    ) -> Event:
        """
        Construye y publica un evento en una sola llamada.

        Devuelve el evento para que quien lo emitió pueda usar su `id` como
        `cause_id` de los eventos que provoque.
        """
        event = Event(
            entity_id=entity_id,
            type=type,
            payload=payload or {},
            cause_id=cause_id,
        )
        return self.publish(event)
