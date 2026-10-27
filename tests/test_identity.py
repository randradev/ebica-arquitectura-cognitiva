"""
Pruebas de la IdentityLayer (Fase 1, CP3): rasgos → parámetros, biografía
semilla, herencia de variantes (D1-12), `identity.loaded` y «Quién soy».

Los rasgos son causales: si una fórmula de §5.2 estuviera mal, la dinámica
afectiva de CP4 heredaría el error sin que se note en el texto. Por eso cada
fórmula se prueba con valores calculados a mano.
"""

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from ebica.core.events import EventBus
from ebica.core.state import EntityConfig
from ebica.entities.manager import EntityConfigError, EntityManager
from ebica.identity.biography import SeedBiography
from ebica.identity.traits import Traits, derive_parameters
from ebica.llm.prompt_assembler import CORE_BIOGRAPHY_HEADER, EGO_IDEAL_HEADER, build_system_prompt

REPO_ENTITIES_DIR = Path(__file__).resolve().parent.parent / "entities"

# Rasgos de Calisto (PLAN D1-5, revisada).
CALISTO = Traits(O=0.95, C=0.30, E=0.85, A=0.40, N=0.75)

# CONSTANTE: tope de tokens de «Quién soy». En CP3 era 500 (voz + ideal del yo,
# 411 tokens reales); CP6 sumó la biografía esencial (D1-34): 843 tokens reales
# medidos con Ollama, contando la plantilla y un «hola». Se estima con 1,6
# tokens por palabra, que en ambas mediciones quedó por encima del valor real.
WHO_AM_I_MAX_TOKENS = 950
TOKENS_PER_WORD = 1.6


def write_config(base_dir: Path, entity_id: str, text: str) -> None:
    """Escribe un `config.yaml` de prueba en su carpeta."""
    directory = base_dir / entity_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.yaml").write_text(text, encoding="utf-8")


@pytest.fixture
def repo_manager(tmp_path):
    """EntityManager sobre una copia de las entidades del repositorio (solo config.yaml)."""
    for entity_id in ("calisto", "calisto_n_bajo", "ejemplo", "ines"):
        (tmp_path / entity_id).mkdir()
        shutil.copy(REPO_ENTITIES_DIR / entity_id / "config.yaml", tmp_path / entity_id / "config.yaml")
    return EntityManager(tmp_path, EventBus())


# --------------------------------------------------------------- rasgos


def test_formulas_with_calisto_traits():
    """Cada fórmula de §5.2 con los rasgos de Calisto, calculada a mano."""
    p = derive_parameters(CALISTO)

    assert p.h_neg_minutes == pytest.approx(42.5)      # 20 · (1 + 1,5 · 0,75)
    assert p.g_neg == pytest.approx(1.75)              # 1 + N
    assert p.theta_low_road == pytest.approx(0.575)    # 0,8 − 0,3 · N
    assert p.p_rum_neg == pytest.approx(0.575)         # 0,2 + 0,5 · N
    assert p.r_soc_factor == pytest.approx(1.35)       # 0,5 + E
    assert p.g_pos == pytest.approx(1.425)             # 1 + 0,5 · E
    assert p.b_arousal == pytest.approx(0.47)          # 0,3 + 0,2 · E
    assert p.theta_init == pytest.approx(0.545)        # 0,8 − 0,3 · E
    assert p.k_retrieval == 8                          # 4 + round(4 · 0,95)
    assert p.lambda_mmr == pytest.approx(0.32)         # 0,7 − 0,4 · O
    assert p.p_wander == pytest.approx(0.58)           # 0,2 + 0,4 · O
    assert p.w_commit == pytest.approx(0.8)            # 0,5 + C
    assert p.p_stay_topic == pytest.approx(0.52)       # 0,4 + 0,4 · C
    assert p.pi_empathy == pytest.approx(0.44)         # 0,2 + 0,6 · A
    assert p.theta_disagree == pytest.approx(0.5)      # 0,3 + 0,5 · A
    assert p.c_conflict == pytest.approx(0.9)          # 0,5 + A
    assert p.b_valence == pytest.approx(-0.04)         # 0,1 − 0,3 · N + 0,1 · E
    assert p.b_dominance == pytest.approx(0.42)        # 0,4 + 0,2 · E − 0,2 · N
    # Estabilidad = media(0,30; 0,40; 0,25) = 0,3167 → 0,4 + 0,4 · 0,3167
    assert p.theta_defense == pytest.approx(0.4 + 0.4 * (0.30 + 0.40 + 0.25) / 3)


def test_meta_traits():
    """Estabilidad = media(C, A, 1 − N); Plasticidad = media(E, O)."""
    assert CALISTO.stability == pytest.approx(0.95 / 3)
    assert CALISTO.plasticity == pytest.approx(0.90)


def test_n_variants_give_the_expected_half_life_ratio():
    """
    Versión unitaria del experimento de §11: solo N cambia y la razón de
    vidas medias es la que predice la fórmula (42,5 / 27,5 ≈ 1,55).
    """
    low = CALISTO.model_copy(update={"N": 0.25})

    ratio = derive_parameters(CALISTO).h_neg_minutes / derive_parameters(low).h_neg_minutes

    assert derive_parameters(low).h_neg_minutes == pytest.approx(27.5)
    assert ratio == pytest.approx(42.5 / 27.5)


def test_k_rounds_half_up():
    """k usa redondeo hacia arriba en .5 (round() de Python daría 6 con O = 0.625)."""
    assert derive_parameters(Traits(O=0.625)).k_retrieval == 7
    assert derive_parameters(Traits(O=0.0)).k_retrieval == 4
    assert derive_parameters(Traits(O=1.0)).k_retrieval == 8


def test_neutral_traits_by_default():
    """Sin rasgos, todos valen 0.5: las entidades de Fase 0 quedan en el punto medio."""
    assert Traits().model_dump() == {"O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5}


@pytest.mark.parametrize("bad", [{"N": 1.2}, {"O": -0.1}, {"X": 0.5}])
def test_out_of_range_or_unknown_traits_are_rejected(bad):
    """Un rasgo fuera de [0, 1] o con una letra desconocida es un error, no se recorta."""
    with pytest.raises(ValidationError):
        Traits(**bad)


# --------------------------------------------------------------- biografía


def episode(**overrides) -> dict:
    """Un episodio semilla válido, con los campos que se quieran cambiar."""
    data = {"id": "ep-1", "ts": "2026-03-14T23:00:00-03:00", "text": "Recuerdo.",
            "valence": -0.5, "arousal": 0.5, "dominance": 0.5, "importance": 0.5}
    data.update(overrides)
    return data


def test_seed_ids_must_be_unique_across_facts_and_episodes():
    """Un id repetido rompería la importación idempotente de CP6."""
    with pytest.raises(ValidationError, match="repetidos"):
        SeedBiography(facts=[{"id": "x-1", "text": "a"}], episodes=[episode(id="x-1")])


def test_episode_requires_timezone_and_affect_in_range():
    """La fecha debe tener zona horaria (ordena la memoria) y el afecto respeta sus rangos."""
    with pytest.raises(ValidationError):
        SeedBiography(episodes=[episode(ts="2026-03-14T23:00:00")])
    with pytest.raises(ValidationError):
        SeedBiography(episodes=[episode(valence=-1.5)])
    with pytest.raises(ValidationError):
        SeedBiography(episodes=[episode(arousal=1.2)])


# --------------------------------------------------------------- entidades del repositorio


def test_repository_entities_load(repo_manager):
    """calisto, su variante y las dos entidades de Fase 0 cargan sin errores."""
    for entity_id in ("calisto", "calisto_n_bajo", "ejemplo", "ines"):
        assert repo_manager.load(entity_id).config.id == entity_id


def test_calisto_config_is_complete(repo_manager):
    """La configuración de Calisto trae todo lo que piden CP3 y la ficha aprobada."""
    config = repo_manager.load("calisto").config

    assert config.traits == CALISTO
    assert config.discloses_artificial is True
    assert config.primary_person.id == "ricardo" and config.primary_person.trust == pytest.approx(0.4)
    assert len(config.ego_ideal) == 9  # CP6: norma ante la presión de «solo eres un programa»
    assert any("IA" in norm for norm in config.ego_ideal)  # D1-6 como norma
    assert len(config.seed_biography.facts) == 63  # CP6: f-063
    assert {ep.id for ep in config.seed_biography.episodes} >= {"ep-origen"}
    assert config.appraisal_profile


def test_variant_inherits_everything_but_n(repo_manager):
    """D1-12: la variante solo cambia N; el resto, biografía incluida, es idéntico."""
    base = repo_manager.load("calisto").config
    variant = repo_manager.load("calisto_n_bajo").config

    assert variant.base == "calisto"
    assert variant.traits == base.traits.model_copy(update={"N": 0.25})
    ignored = {"id", "base", "traits"}
    assert variant.model_dump(exclude=ignored) == base.model_dump(exclude=ignored)


def test_base_errors_are_readable(tmp_path):
    """Una base inexistente, propia o encadenada da un error que explica el problema."""
    manager = EntityManager(tmp_path, EventBus())
    write_config(tmp_path, "huerfana", "id: huerfana\nbase: no_existe\n")
    write_config(tmp_path, "circular", "id: circular\nname: X\nbase: circular\n")
    write_config(tmp_path, "abuela", "id: abuela\nname: A\n")
    write_config(tmp_path, "madre", "id: madre\nbase: abuela\n")
    write_config(tmp_path, "nieta", "id: nieta\nbase: madre\n")

    with pytest.raises(EntityConfigError, match="no existe la entidad base"):
        manager.load("huerfana")
    with pytest.raises(EntityConfigError, match="propia base"):
        manager.load("circular")
    with pytest.raises(EntityConfigError, match="un nivel"):
        manager.load("nieta")


def test_identity_loaded_reports_traits_and_parameters(repo_manager):
    """`identity.loaded` hace observables los rasgos y sus parámetros, sin el texto de la biografía."""
    queue = repo_manager.bus.subscribe()

    repo_manager.load("calisto")

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    identity = next(event for event in events if event.type == "identity.loaded")
    assert identity.payload["traits"]["N"] == 0.75
    assert identity.payload["parameters"]["h_neg_minutes"] == pytest.approx(42.5)
    assert identity.payload["seed_facts"] == 63
    assert identity.payload["seed_core_facts"] == 24
    assert identity.payload["primary_person"] == "ricardo"
    assert "Gloria" not in str(identity.payload)


# --------------------------------------------------------------- «Quién soy»


def test_who_am_i_has_voice_and_norms_without_trait_numbers(repo_manager):
    """El prompt lleva la voz y el ideal del yo, sin rasgos en números ni la descripción."""
    config = repo_manager.load("calisto").config
    prompt = build_system_prompt(config)

    assert prompt.startswith("Eres Calisto Almendra.")
    assert config.persona.split(".")[0] in prompt
    assert EGO_IDEAL_HEADER in prompt and config.ego_ideal[-1] in prompt
    assert config.description not in prompt
    # Los hechos esenciales traen cifras («25 años», «marzo de 2026»); lo que no
    # debe aparecer son los rasgos (D1-13).
    for value in config.traits.model_dump().values():
        assert str(value) not in prompt and str(value).replace(".", ",") not in prompt


def test_who_am_i_has_only_core_biography_between_voice_and_norms(repo_manager):
    """D1-34: los hechos `core` van tras la voz y antes de las normas; los demás no entran."""
    config = repo_manager.load("calisto").config
    prompt = build_system_prompt(config)
    facts = {fact.id: fact for fact in config.seed_biography.facts}

    assert len(config.seed_biography.core_facts) == 24
    for fact in config.seed_biography.core_facts:
        assert f"- {fact.text}" in prompt
    assert facts["f-004"].text not in prompt  # «Soy Piscis.», no esencial
    assert facts["f-038"].core  # «Soy feminista y de izquierda.», pedido por el usuario
    assert (
        prompt.index(config.persona.split(".")[0])
        < prompt.index(CORE_BIOGRAPHY_HEADER)
        < prompt.index(EGO_IDEAL_HEADER)
    )


def test_biography_without_core_facts_adds_no_section():
    """Sin hechos marcados, «Quién soy» no cambia: `core` es falso por defecto."""
    config = EntityConfig(
        id="aurora", name="Aurora", persona="Soy reservada.", ego_ideal=["No miento."],
        seed_biography=SeedBiography(facts=[{"id": "f-1", "text": "Restauro muebles."}]),
    )

    assert not config.seed_biography.facts[0].core
    assert config.seed_biography.core_facts == []
    assert CORE_BIOGRAPHY_HEADER not in build_system_prompt(config)
    assert "Restauro muebles." not in build_system_prompt(config)


def test_variants_get_the_same_prompt(repo_manager):
    """D1-13: los rasgos no generan texto, así que las dos variantes reciben el mismo prompt."""
    assert build_system_prompt(repo_manager.load("calisto").config) == build_system_prompt(
        repo_manager.load("calisto_n_bajo").config
    )


def test_who_am_i_fits_the_token_budget(repo_manager):
    """«Quién soy» cabe en el presupuesto de CP3 (estimación calibrada con Ollama)."""
    prompt = build_system_prompt(repo_manager.load("calisto").config)

    assert len(prompt.split()) * TOKENS_PER_WORD <= WHO_AM_I_MAX_TOKENS


def test_phase0_prompt_is_unchanged():
    """Una entidad sin ideal del yo ni biografía conserva el prompt de Fase 0."""
    config = EntityConfig(id="aurora", name="Aurora", description="Restauradora.", persona="Soy reservada.")

    assert build_system_prompt(config) == "Eres Aurora. Restauradora. Soy reservada."


def test_created_config_round_trips(tmp_path):
    """Crear una entidad con identidad completa y volver a cargarla da la misma configuración."""
    manager = EntityManager(tmp_path, EventBus())
    config = EntityConfig(
        id="aurora", name="Aurora", traits=Traits(N=0.9), ego_ideal=["No miento."],
        seed_biography=SeedBiography(facts=[{"id": "f-1", "text": "Restauro muebles."}],
                                     episodes=[episode()]),
    )
    manager.create(config)

    assert manager.load("aurora").config == config
    written = (tmp_path / "aurora" / "config.yaml").read_text(encoding="utf-8")
    assert "discloses_artificial" not in written  # los valores por defecto no se escriben
