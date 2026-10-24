"""Pruebas de EntityConfig, EntityState y EntityManager (CP2)."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from ebica.core.events import EventBus, JsonlEventLog
from ebica.core.state import EntityConfig, EntityState
from ebica.entities.manager import EntityConfigError, EntityManager

# Carpeta real de entidades del repositorio (solo se lee, nunca se escribe).
REPO_ENTITIES_DIR = Path(__file__).resolve().parent.parent / "entities"


@pytest.fixture
def bus():
    """Bus sin persistencia: estas pruebas miran los eventos por la cola."""
    return EventBus()


@pytest.fixture
def manager(tmp_path, bus):
    """EntityManager sobre una carpeta temporal, para no tocar `entities/`."""
    return EntityManager(tmp_path, bus)


def make_config(entity_id: str = "aurora") -> EntityConfig:
    """Construye una configuración válida de prueba."""
    return EntityConfig(id=entity_id, name="Aurora", description="Prueba", persona="Soy Aurora.")


def write_config(base_dir: Path, entity_id: str, text: str) -> None:
    """Escribe a mano un `config.yaml`, para probar archivos inválidos."""
    directory = base_dir / entity_id
    directory.mkdir(parents=True)
    (directory / "config.yaml").write_text(text, encoding="utf-8")


def test_create_writes_config_and_state(manager, tmp_path):
    """Crear una entidad deja `config.yaml` y `state.json` en su carpeta."""
    manager.create(make_config())

    directory = tmp_path / "aurora"
    assert (directory / "config.yaml").exists()
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    assert state["entity_id"] == "aurora"
    assert state["mode"] == "wake"
    assert state["last_loaded_at"] is None


def test_create_emits_entity_created(manager, bus):
    """Crear una entidad emite `entity.created` con su nombre."""
    queue = bus.subscribe()

    manager.create(make_config())

    event = queue.get_nowait()
    assert event.type == "entity.created"
    assert event.entity_id == "aurora"
    assert event.payload == {"name": "Aurora"}


def test_create_refuses_existing_entity(manager):
    """No se puede crear dos veces la misma entidad (protege su historia)."""
    manager.create(make_config())

    with pytest.raises(FileExistsError):
        manager.create(make_config())


def test_load_rebuilds_created_entity(manager, bus):
    """Cargar devuelve la misma configuración y el estado guardado, y emite `entity.loaded`."""
    created = manager.create(make_config())
    queue = bus.subscribe()

    loaded = manager.load("aurora")

    assert loaded.config == created.config
    assert loaded.state.created_at == created.state.created_at
    assert loaded.state.last_loaded_at is not None
    event = queue.get_nowait()
    assert event.type == "entity.loaded"
    assert event.payload == {"name": "Aurora", "mode": "wake", "state_existed": True}


def test_load_persists_last_loaded_at(manager):
    """La hora de carga se guarda en `state.json` y sobrevive a otra carga."""
    manager.create(make_config())
    first = manager.load("aurora")

    second = manager.load("aurora")

    assert second.state.last_loaded_at >= first.state.last_loaded_at
    assert second.state.created_at == first.state.created_at


def test_load_without_state_creates_initial_state(manager, tmp_path):
    """Una entidad con solo `config.yaml` (como en el repo) se carga con estado inicial."""
    write_config(tmp_path, "solo_config", "id: solo_config\nname: Solo\n")

    loaded = manager.load("solo_config")

    assert loaded.state.entity_id == "solo_config"
    assert (tmp_path / "solo_config" / "state.json").exists()


def test_load_writes_events_to_jsonl(tmp_path):
    """Con un bus persistente, `entity.created` y `entity.loaded` quedan en el JSONL."""
    log = JsonlEventLog(tmp_path)
    manager = EntityManager(tmp_path, EventBus(log))
    manager.create(make_config())
    loaded = manager.load("aurora")

    events = log.read("aurora", loaded.state.last_loaded_at)

    assert [event.type for event in events] == ["entity.created", "entity.loaded"]


def test_missing_required_field_gives_readable_error(manager, tmp_path):
    """Un `config.yaml` sin `name` produce un error que nombra el campo y el archivo."""
    write_config(tmp_path, "sin_nombre", "id: sin_nombre\n")

    with pytest.raises(EntityConfigError) as error:
        manager.load("sin_nombre")

    message = str(error.value)
    assert "'name'" in message
    assert "config.yaml" in message


def test_unknown_field_is_rejected(manager, tmp_path):
    """Un campo desconocido (p. ej. un error de tipeo) no se ignora en silencio."""
    write_config(tmp_path, "tipeo", "id: tipeo\nname: Tipeo\nnmae: X\n")

    with pytest.raises(EntityConfigError, match="'nmae'"):
        manager.load("tipeo")


def test_invalid_yaml_gives_readable_error(manager, tmp_path):
    """Un archivo que no es YAML válido produce `EntityConfigError`, no un error crudo."""
    write_config(tmp_path, "roto", "id: roto\nname: [sin cerrar\n")

    with pytest.raises(EntityConfigError, match="no es YAML válido"):
        manager.load("roto")


def test_id_must_match_folder(manager, tmp_path):
    """El id del archivo debe coincidir con la carpeta, o se mezclarían datos."""
    write_config(tmp_path, "carpeta", "id: otro\nname: Otro\n")

    with pytest.raises(EntityConfigError, match="no coincide"):
        manager.load("carpeta")


def test_missing_entity_gives_readable_error(manager):
    """Cargar una entidad inexistente produce `EntityConfigError`."""
    with pytest.raises(EntityConfigError, match="No existe"):
        manager.load("fantasma")


def test_invalid_entity_id_is_rejected():
    """El id de la configuración usa el mismo formato seguro que los eventos."""
    with pytest.raises(ValidationError):
        EntityConfig(id="../fuera", name="X")


def test_invalid_mode_is_rejected():
    """El estado solo admite los modos de la máquina de estados (§6.7)."""
    with pytest.raises(ValidationError):
        EntityState(entity_id="aurora", mode="dreaming")


def test_example_entity_loads(tmp_path, bus):
    """La entidad de ejemplo del repositorio es válida (se copia a una carpeta temporal)."""
    shutil.copytree(REPO_ENTITIES_DIR / "ejemplo", tmp_path / "ejemplo")
    manager = EntityManager(tmp_path, bus)

    loaded = manager.load("ejemplo")

    assert loaded.config.name == "Ejemplo"
