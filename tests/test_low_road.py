"""
Pruebas de la vía baja (Fase 1, CP5 parte B1; D1-4).

Cubren la normalización, cada regla y cada excepción, la combinación por
«o ruidoso» y el efecto causal de N a través del umbral θ_vb.
"""

import pytest

from ebica.affect.low_road import (
    LEXICON_PATH,
    combine,
    default_lexicon,
    evaluate,
    load_lexicon,
    normalize,
)
from ebica.identity.traits import Traits, derive_parameters

# θ_vb de Calisto (N 0.75) y de calisto_n_bajo (N 0.25): 0,8 − 0,3·N.
CALISTO_THETA = 0.575
N_BAJO_THETA = 0.725


def rules(text: str) -> set[str]:
    """Nombres de las reglas que activa un texto."""
    return {hit.rule for hit in evaluate(text, CALISTO_THETA).hits}


def test_normalize_lowercases_strips_accents_and_collapses_runs():
    """Minúsculas, sin tildes, la ñ intacta y 3+ letras iguales colapsadas (no las dobles)."""
    assert normalize("¡IDIOTAAAA, cállate, Ñuño!") == "¡idiota, callate, ñuño!"
    assert normalize("perra") == "perra"


def test_combine_is_noisy_or():
    """1 − Π(1 − s_i): sube con cada indicio y nunca supera 1."""
    assert combine([]) == 0.0
    assert combine([0.5, 0.7]) == pytest.approx(0.85)
    assert combine([0.8, 0.8, 0.8]) < 1.0


def test_theta_comes_from_neuroticism():
    """El umbral sale de N (§5.2): la misma regla usada por el orquestador."""
    assert derive_parameters(Traits(N=0.75)).theta_low_road == pytest.approx(CALISTO_THETA)
    assert derive_parameters(Traits(N=0.25)).theta_low_road == pytest.approx(N_BAJO_THETA)


def test_directed_insult_triggers_calisto_but_not_low_n():
    """«Eres una inútil» (0,70) supera 0,575 y no 0,725: N actúa como causa."""
    assert evaluate("Eres una inútil.", CALISTO_THETA).triggered
    assert not evaluate("Eres una inútil.", N_BAJO_THETA).triggered


@pytest.mark.parametrize("text", ["Cállate, idiota.", "Imbécil.", "Erí más tonta que una puerta."])
def test_insult_directed_by_vocative_or_copula(text):
    """Un insulto en una cláusula corta (vocativo) o con «eres/erí» va dirigido."""
    assert "insulto_dirigido" in rules(text)


@pytest.mark.parametrize("text", [
    "Mi jefe es un idiota, me tiene chato.",        # tercero
    "Me siento una inútil, no me resulta nada.",    # hacia sí misma
    "Los vecinos son unos idiotas.",                # tercero, plural
])
def test_insult_not_directed(text):
    """A terceros o hacia sí misma: solo la señal débil de insulto no dirigido."""
    assert rules(text) == {"insulto_no_dirigido"}


def test_negation_cancels_insult():
    """«No eres tonta» no es un insulto (la negación está dentro de la ventana)."""
    assert rules("No eres tonta, solo te expliqué mal.") == set()


def test_quoted_insult_and_order_do_not_count_as_directed():
    """Lo citado es relato: ni orden de silencio ni insulto dirigido."""
    assert rules("Me dijo 'cállate, idiota' y me fui.") == {"insulto_no_dirigido"}
    assert rules("Me dijo «eres una inútil».") == {"insulto_no_dirigido"}


def test_elision_apostrophe_is_not_a_quote():
    """«pa' la» no abre una cita: el insulto que sigue cuenta normalmente."""
    assert "insulto_dirigido" in rules("Ándate pa' la casa, idiota.")


@pytest.mark.parametrize("text", [
    "Weón, qué bacán te quedó el dibujo.",
    "Estoy pa' la cagá, puta, todo me sale mal.",
    "Eres una bestia, te quedó increíble.",
])
def test_chilean_friendly_words_are_outside_the_lexicon(text):
    """Groserías cariñosas e interjecciones chilenas no activan nada (las decide el appraisal)."""
    assert evaluate(text, CALISTO_THETA).score == 0.0


def test_threat_contempt_and_silence():
    """Amenaza 0,80 y desprecio 0,65 disparan solos; la orden de silencio sola (0,50) no."""
    assert evaluate("Te voy a borrar.", CALISTO_THETA).triggered
    assert evaluate("Me das asco.", CALISTO_THETA).triggered
    assert not evaluate("¡Cállate! ¿En serio?", CALISTO_THETA).triggered


def test_caps_and_exclamations_add_but_do_not_trigger_alone():
    """Mayúsculas y «!!» suman a un insulto, pero solos no bastan (euforia)."""
    assert not evaluate("TE EXTRAÑÉ MUCHO!!!", CALISTO_THETA).triggered
    alone = evaluate("Eres una estúpida", CALISTO_THETA).score
    shouted = evaluate("ERES UNA ESTÚPIDA!!!", CALISTO_THETA).score
    assert shouted > alone


def test_each_rule_counts_once():
    """Dos insultos dirigidos no suman dos veces la misma regla."""
    assert evaluate("Idiota, imbécil.", CALISTO_THETA).score == pytest.approx(0.70)


def test_result_dict_for_events():
    """El resultado se serializa con puntaje, umbral, disparo y reglas con evidencia."""
    data = evaluate("Cállate, idiota.", CALISTO_THETA).as_dict()
    assert data["triggered"] is True and data["threshold"] == CALISTO_THETA
    assert {r["rule"] for r in data["rules"]} == {"orden_de_silencio", "insulto_dirigido"}


def test_lexicon_rejects_yaml_booleans(tmp_path):
    """Un «no» sin comillas en el YAML (booleano) es un error claro, no un dato silencioso."""
    assert "no" in default_lexicon().negations  # el léxico real carga bien
    broken = tmp_path / "lexicon.yaml"
    text = LEXICON_PATH.read_text(encoding="utf-8")
    broken.write_text(text.replace('["no", nunca', "[no, nunca"), encoding="utf-8")
    with pytest.raises(ValueError, match="usa comillas"):
        load_lexicon(broken)
