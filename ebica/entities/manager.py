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
from ebica.identity.traits import derive_parameters

CONFIG_FILENAME = "config.yaml"
STATE_FILENAME = "state.json"


def identity_payload(config: EntityConfig) -> dict:
    """
    Contenido del evento `identity.loaded` (§5.2): rasgos y parámetros derivados.

    Hace observable en la consola cómo la personalidad se traduce en números
    (p. ej. N 0.75 → vida media del ánimo negativo de 42,5 min). No incluye el
    texto de la biografía, solo cuántos hechos y episodios tiene.
    """
    traits = config.traits
    return {
        "base": config.base,
        "traits": traits.model_dump(),
        "stability": traits.stability,
        "plasticity": traits.plasticity,
        "parameters": derive_parameters(traits).as_dict(),
        "ego_ideal_norms": len(config.ego_ideal),
        "seed_facts": len(config.seed_biography.facts),
        "seed_episodes": len(config.seed_biography.episodes),
        "primary_person": config.primary_person.id if config.primary_person else None,
        "discloses_artificial": config.discloses_artificial,
    }


class EntityConfigError(ValueError):
    """Un `config.yaml` no existe, no es YAML válido o no cumple el esquema."""


def _merge(base: dict, override: dict) -> dict:
    """
    Fusiona dos configuraciones: lo de `override` gana.

    Los mapas se fusionan campo a campo (`traits: {N: 0.25}` cambia solo N);
    cualquier otro valor, listas incluidas, se reemplaza entero.
    """
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


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
            # respeta el orden de los campos del esquema. exclude_defaults
            # escribe solo lo que la entidad define (no rasgos neutros ni
            # listas vacías); mode="json" deja las fechas como texto ISO.
            yaml.safe_dump(
                config.model_dump(mode="json", exclude_defaults=True),
                file, allow_unicode=True, sort_keys=False,
            )

        state = EntityState(entity_id=config.id)
        self.save_state(state)
        self.bus.emit(config.id, "entity.created", {"name": config.name})
        return Entity(config=config, state=state)

    def load(self, entity_id: str) -> Entity:
        """
        Carga una entidad existente desde su carpeta.

        Valida `config.yaml`; reconstruye el estado desde `state.json` o, si no
        existe (p. ej. una entidad recién clonada del repositorio, donde solo se
        versiona la configuración), crea uno inicial. Registra la hora de carga,
        guarda el estado y emite `entity.loaded` e `identity.loaded`.
        """
        config = self.read_config(entity_id)

        state_path = self.entity_dir(entity_id) / STATE_FILENAME
        state_existed = state_path.exists()
        if state_existed:
            state = EntityState.model_validate_json(state_path.read_text(encoding="utf-8"))
        else:
            state = EntityState(entity_id=entity_id)

        state.last_loaded_at = datetime.now(timezone.utc)
        self.save_state(state)
        self.bus.emit(
            entity_id,
            "entity.loaded",
            {"name": config.name, "mode": state.mode, "state_existed": state_existed},
        )
        self.bus.emit(entity_id, "identity.loaded", identity_payload(config))
        return Entity(config=config, state=state)

    def read_config(self, entity_id: str) -> EntityConfig:
        """
        Lee y valida el `config.yaml` de una entidad, ya fusionado con su base.

        No tiene efectos secundarios (no escribe estado ni emite eventos), así
        que sirve también para scripts como el benchmark de appraisal. Traduce
        los errores de archivo, de YAML y de Pydantic a un único
        `EntityConfigError` con un mensaje legible que indica la ruta y los campos.
        """
        # El id puede venir de una URL de la API: se valida antes de usarlo como
        # ruta, para que algo como "../otra_carpeta" no lea fuera de `base_dir`.
        if not re.fullmatch(ENTITY_ID_PATTERN, entity_id):
            raise EntityConfigError(f"Id de entidad inválido: '{entity_id}'")
        path = self.entity_dir(entity_id) / CONFIG_FILENAME
        if not path.exists():
            raise EntityConfigError(f"No existe {path}")

        data = self._read_yaml(path)
        if data.get("base") is not None:
            data = self._merge_with_base(entity_id, data)

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

    @staticmethod
    def _read_yaml(path: Path) -> dict:
        """Lee un `config.yaml` como diccionario, con errores legibles."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise EntityConfigError(f"{path} no es YAML válido: {error}") from error
        if not isinstance(data, dict):
            raise EntityConfigError(f"{path} debe contener un mapa de campos (clave: valor)")
        return data

    def _merge_with_base(self, entity_id: str, data: dict) -> dict:
        """
        Completa una variante con los campos de su entidad base (D1-12).

        Permite definir, p. ej., `calisto_n_bajo` con solo `base: calisto` y
        `traits: {N: 0.25}`, sin copiar la biografía: una sola fuente de
        verdad. Solo un nivel de herencia, para que sea evidente de dónde
        sale cada campo. No es clonación (Fase 2): no copia memoria ni estado.
        """
        base_id = data["base"]
        if not isinstance(base_id, str) or not re.fullmatch(ENTITY_ID_PATTERN, base_id):
            raise EntityConfigError(f"{entity_id}: base inválida: '{base_id}'")
        if base_id == entity_id:
            raise EntityConfigError(f"{entity_id}: una entidad no puede ser su propia base")
        base_path = self.entity_dir(base_id) / CONFIG_FILENAME
        if not base_path.exists():
            raise EntityConfigError(f"{entity_id}: no existe la entidad base {base_path}")
        base_data = self._read_yaml(base_path)
        if base_data.get("base") is not None:
            raise EntityConfigError(
                f"{entity_id}: la base '{base_id}' tiene a su vez otra base; solo se admite un nivel"
            )
        return _merge(base_data, data)

    def save_state(self, state: EntityState) -> None:
        """
        Guarda el estado en `state.json` de forma atómica.

        Escribe primero un archivo temporal y luego lo reemplaza: si el proceso
        se interrumpe a mitad, el `state.json` anterior queda intacto.
        """
        path = self.entity_dir(state.entity_id) / STATE_FILENAME
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
