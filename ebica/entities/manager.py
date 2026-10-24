"""
EntityManager: crea y carga entidades desde disco (documento base §5.1, D1).

Cada entidad vive en su propia carpeta, separada del código del motor:

    <base_dir>/<entity_id>/config.yaml   definición (se versiona)
    <base_dir>/<entity_id>/state.json    estado vivo (no se versiona)
    <base_dir>/<entity_id>/events/       registro JSONL (no se versiona)

Suspender, clonar y eliminar llegan en fases posteriores.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from ebica.core.events import ENTITY_ID_PATTERN, EventBus
from ebica.core.state import EntityConfig, EntityState

CONFIG_FILENAME = "config.yaml"
STATE_FILENAME = "state.json"


class EntityConfigError(ValueError):
    """Un `config.yaml` no existe, no es YAML válido o no cumple el esquema."""


@dataclass
class Entity:
    """Una entidad cargada en memoria: su configuración y su estado."""

    config: EntityConfig
    state: EntityState


class EntityManager:
    """Crea y carga entidades bajo una carpeta raíz, emitiendo sus eventos."""

    def __init__(self, base_dir: Path, bus: EventBus) -> None:
        """Guarda la carpeta raíz de las entidades y el bus donde emitir eventos."""
        self.base_dir = Path(base_dir)
        self.bus = bus

    def entity_dir(self, entity_id: str) -> Path:
        """Devuelve la carpeta de una entidad (exista o no)."""
        return self.base_dir / entity_id

    def list_ids(self) -> list[str]:
        """Devuelve, ordenados, los ids de las carpetas que contienen un `config.yaml`."""
        if not self.base_dir.exists():
            return []
        return sorted(
            path.name for path in self.base_dir.iterdir() if (path / CONFIG_FILENAME).is_file()
        )

    def create(self, config: EntityConfig) -> Entity:
        """
        Crea una entidad nueva: escribe `config.yaml` y un `state.json` inicial.

        Falla con `FileExistsError` si ya existe una entidad con ese id, para no
        sobrescribir la historia de otra. Emite `entity.created`.
        """
        directory = self.entity_dir(config.id)
        config_path = directory / CONFIG_FILENAME
        if config_path.exists():
            raise FileExistsError(f"Ya existe una entidad con id '{config.id}' en {directory}")

        directory.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            # allow_unicode conserva tildes y eñes legibles; sort_keys=False
            # respeta el orden de los campos del esquema.
            yaml.safe_dump(config.model_dump(), file, allow_unicode=True, sort_keys=False)

        state = EntityState(entity_id=config.id)
        self._save_state(state)
        self.bus.emit(config.id, "entity.created", {"name": config.name})
        return Entity(config=config, state=state)

    def load(self, entity_id: str) -> Entity:
        """
        Carga una entidad existente desde su carpeta.

        Valida `config.yaml`; reconstruye el estado desde `state.json` o, si no
        existe (p. ej. una entidad recién clonada del repositorio, donde solo se
        versiona la configuración), crea uno inicial. Registra la hora de carga,
        guarda el estado y emite `entity.loaded`.
        """
        config = self._read_config(entity_id)

        state_path = self.entity_dir(entity_id) / STATE_FILENAME
        state_existed = state_path.exists()
        if state_existed:
            state = EntityState.model_validate_json(state_path.read_text(encoding="utf-8"))
        else:
            state = EntityState(entity_id=entity_id)

        state.last_loaded_at = datetime.now(timezone.utc)
        self._save_state(state)
        self.bus.emit(
            entity_id,
            "entity.loaded",
            {"name": config.name, "mode": state.mode, "state_existed": state_existed},
        )
        return Entity(config=config, state=state)

    def _read_config(self, entity_id: str) -> EntityConfig:
        """
        Lee y valida el `config.yaml` de una entidad.

        Traduce los errores de archivo, de YAML y de Pydantic a un único
        `EntityConfigError` con un mensaje legible que indica la ruta y los campos.
        """
        # El id puede venir de una URL de la API: se valida antes de usarlo como
        # ruta, para que algo como "../otra_carpeta" no lea fuera de `base_dir`.
        if not re.fullmatch(ENTITY_ID_PATTERN, entity_id):
            raise EntityConfigError(f"Id de entidad inválido: '{entity_id}'")
        path = self.entity_dir(entity_id) / CONFIG_FILENAME
        if not path.exists():
            raise EntityConfigError(f"No existe {path}")

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise EntityConfigError(f"{path} no es YAML válido: {error}") from error
        if not isinstance(data, dict):
            raise EntityConfigError(f"{path} debe contener un mapa de campos (clave: valor)")

        try:
            config = EntityConfig.model_validate(data)
        except ValidationError as error:
            problems = "; ".join(
                f"'{'.'.join(str(part) for part in issue['loc'])}': {issue['msg']}"
                for issue in error.errors()
            )
            raise EntityConfigError(f"{path} no es válido: {problems}") from error

        # El id de la carpeta y el del archivo deben coincidir: los eventos y
        # la memoria se indexan por entity_id, y una discrepancia los mezclaría.
        if config.id != entity_id:
            raise EntityConfigError(
                f"{path}: el id '{config.id}' no coincide con la carpeta '{entity_id}'"
            )
        return config

    def _save_state(self, state: EntityState) -> None:
        """
        Guarda el estado en `state.json` de forma atómica.

        Escribe primero un archivo temporal y luego lo reemplaza: si el proceso
        se interrumpe a mitad, el `state.json` anterior queda intacto.
        """
        path = self.entity_dir(state.entity_id) / STATE_FILENAME
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
