"""
DriveSystem, el «Ello» (documento base §5.3; Fase 1: `social`, `novelty`, `rest`).

Un drive es una necesidad homeostática con un error `e ∈ [0, 1]` que crece solo
si no se atiende (`e += r·dt`). Acople con el afecto (Solms):

    Δvalence = −Σ wᵢ · Δeᵢ

Que una necesidad crezca baja el ánimo; que se satisfaga (Δe < 0) lo sube.
Así, la misma fórmula produce el malestar de la espera y el placer del alivio.

En CP4 los drives solo cambian con el tiempo; la satisfacción (el contacto
satisface `social`, la novedad satisface `novelty`) llega en CP5. Los valores
son los de D1-16, calibrables.
"""

from dataclasses import dataclass

from ebica.identity.traits import DerivedParameters

DRIVE_NAMES = ("social", "novelty", "rest")

# CONSTANTES: horas para ir de 0 a 1 sin satisfacción (D1-16).
# `social` se multiplica además por el factor de E (r_soc = r0 · (0.5 + E)):
# Calisto (E 0.85) llega al máximo en 12 / 1,35 ≈ 8,9 h.
SOCIAL_FULL_HOURS = 12.0
NOVELTY_FULL_HOURS = 24.0
# `rest` crece mientras la entidad está despierta (cargada).
REST_FULL_HOURS = 16.0
# CONSTANTE: descargada, `rest` se recupera con esta vida media; sustituye al
# sueño hasta Fase 2 (D1-7).
REST_RECOVERY_HALF_LIFE_HOURS = 2.0

# CONSTANTES: peso de cada drive en el acople con la valencia (D1-16).
COUPLING_WEIGHTS = {"social": 0.3, "novelty": 0.15, "rest": 0.2}

# CONSTANTE: nivel que dispara `drive.threshold_crossed` (al subir o bajar).
# En CP10, `homeostasis_watch` lo usará como señal.
DRIVE_THRESHOLD = 0.7

# CONSTANTE: niveles de una entidad nueva (D1-16).
INITIAL_DRIVES = {"social": 0.2, "novelty": 0.2, "rest": 0.0}


@dataclass(frozen=True)
class DriveDynamics:
    """Tasas de crecimiento de cada drive, por segundo."""

    rates: dict[str, float]

    @classmethod
    def from_parameters(cls, parameters: DerivedParameters) -> "DriveDynamics":
        """Calcula las tasas; `social` depende de E por `r_soc_factor` (§5.2)."""
        return cls(rates={
            "social": _rate_per_second(SOCIAL_FULL_HOURS) * parameters.r_soc_factor,
            "novelty": _rate_per_second(NOVELTY_FULL_HOURS),
            "rest": _rate_per_second(REST_FULL_HOURS),
        })


def _rate_per_second(full_hours: float) -> float:
    """Tasa que lleva un drive de 0 a 1 en `full_hours` horas."""
    return 1.0 / (full_hours * 3600.0)


def advance_drives(
    drives: dict[str, float], dynamics: DriveDynamics, dt_seconds: float, awake: bool
) -> dict[str, float]:
    """
    Devuelve los drives tras `dt_seconds`, recortados a [0, 1].

    Despierta, todos crecen. Descargada (`awake=False`), `social` y `novelty`
    siguen creciendo, pero `rest` se recupera: es el sustituto del sueño.
    """
    if dt_seconds <= 0:
        return dict(drives)
    advanced = {}
    for name in DRIVE_NAMES:
        level = drives.get(name, INITIAL_DRIVES[name])
        if name == "rest" and not awake:
            level *= 0.5 ** (dt_seconds / (REST_RECOVERY_HALF_LIFE_HOURS * 3600.0))
        else:
            level += dynamics.rates[name] * dt_seconds
        advanced[name] = max(0.0, min(1.0, level))
    return advanced


def valence_coupling(before: dict[str, float], after: dict[str, float]) -> float:
    """Impulso de valencia por el cambio de los drives: Δvalence = −Σ w·Δe."""
    return -sum(weight * (after[name] - before[name]) for name, weight in COUPLING_WEIGHTS.items())


def crossed_thresholds(before: dict[str, float], after: dict[str, float]) -> list[tuple[str, str]]:
    """Drives que cruzaron `DRIVE_THRESHOLD`, con la dirección ("up" o "down")."""
    crossings = []
    for name in DRIVE_NAMES:
        if before[name] < DRIVE_THRESHOLD <= after[name]:
            crossings.append((name, "up"))
        elif after[name] < DRIVE_THRESHOLD <= before[name]:
            crossings.append((name, "down"))
    return crossings
