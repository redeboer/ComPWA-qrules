"""Default configuration for `qrules`.

It is possible to change some settings from the outside, for instance:

>>> import qrules
>>> qrules.settings.MAX_ANGULAR_MOMENTUM = 4
>>> qrules.settings.MAX_SPIN_MAGNITUDE = 3
"""

from __future__ import annotations

import multiprocessing
from copy import deepcopy
from enum import Enum, auto
from fractions import Fraction
from os.path import dirname, join, realpath
from typing import TYPE_CHECKING, Any, Callable

from qrules.conservation_rules import (
    BaryonNumberConservation,
    BottomnessConservation,
    ChargeConservation,
    CharmConservation,
    ConservationRule,
    EdgeQNConservationRule,
    ElectronLNConservation,
    GraphElementRule,
    MassConservation,
    MuonLNConservation,
    StrangenessConservation,
    TauLNConservation,
    c_parity_conservation,
    clebsch_gordan_helicity_to_canonical,
    g_parity_conservation,
    gellmann_nishijima,
    helicity_conservation,
    identical_particle_symmetrization,
    isospin_conservation,
    isospin_validity,
    ls_spin_validity,
    parity_conservation,
    parity_conservation_helicity,
    spin_conservation,
    spin_magnitude_conservation,
    spin_validity,
)
from qrules.quantum_numbers import EdgeQuantumNumbers as EdgeQN
from qrules.quantum_numbers import NodeQuantumNumbers as NodeQN
from qrules.quantum_numbers import arange
from qrules.solving import EdgeSettings, NodeSettings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qrules.particle import Particle, ParticleCollection
    from qrules.transition import SpinFormalism

__QRULES_PATH = dirname(realpath(__file__))
ADDITIONAL_PARTICLES_DEFINITIONS_PATH: str = join(
    __QRULES_PATH, "additional_definitions.yml"
)

CONSERVATION_LAW_PRIORITIES: dict[
    GraphElementRule | EdgeQNConservationRule | ConservationRule, int
] = {
    MassConservation: 10,  # type: ignore[dict-item]
    ElectronLNConservation: 45,  # type: ignore[dict-item]
    MuonLNConservation: 44,  # type: ignore[dict-item]
    TauLNConservation: 43,  # type: ignore[dict-item]
    BaryonNumberConservation: 90,  # type: ignore[dict-item]
    StrangenessConservation: 69,  # type: ignore[dict-item]
    CharmConservation: 70,  # type: ignore[dict-item]
    BottomnessConservation: 68,  # type: ignore[dict-item]
    ChargeConservation: 100,  # type: ignore[dict-item]
    spin_conservation: 8,
    spin_magnitude_conservation: 8,
    parity_conservation: 6,
    c_parity_conservation: 5,
    g_parity_conservation: 3,
    isospin_conservation: 60,
    ls_spin_validity: 89,
    helicity_conservation: 7,
    parity_conservation_helicity: 4,
    identical_particle_symmetrization: 2,
}
"""Determines the order with which to verify conservation rules."""


EDGE_RULE_PRIORITIES: dict[GraphElementRule, int] = {
    gellmann_nishijima: 50,
    isospin_validity: 61,
    spin_validity: 62,
}
"""Determines the order with which to verify `.Edge` conservation rules."""


class InteractionType(Enum):
    """Types of interactions in the form of an enumerate."""

    STRONG = auto()
    EM = auto()
    WEAK = auto()

    @staticmethod
    def from_str(description: str) -> InteractionType:
        description_lower = description.lower()
        if description_lower.startswith("e"):
            return InteractionType.EM
        if description_lower.startswith("s"):
            return InteractionType.STRONG
        if description_lower.startswith("w"):
            return InteractionType.WEAK
        msg = f'Could not determine interaction type from "{description}"'
        raise ValueError(msg)


DEFAULT_INTERACTION_TYPES = [
    InteractionType.STRONG,
    InteractionType.EM,
    InteractionType.WEAK,
]


def create_interaction_settings(  # noqa: PLR0917
    formalism: SpinFormalism,
    particle_db: ParticleCollection,
    nbody_topology: bool = False,
    mass_conservation_factor: float | None = 3.0,
    max_angular_momentum: int = 2,
    max_spin_magnitude: float = 2,
) -> dict[InteractionType, tuple[EdgeSettings, NodeSettings]]:
    """Create a container that holds the settings for `.InteractionType`."""
    formalism_edge_settings = EdgeSettings(
        conservation_rules={
            isospin_validity,
            gellmann_nishijima,
            spin_validity,
        },
        rule_priorities=EDGE_RULE_PRIORITIES,
        qn_domains=_create_domains(particle_db),
    )
    formalism_node_settings = NodeSettings(rule_priorities=CONSERVATION_LAW_PRIORITIES)

    angular_momentum_domain = __get_ang_mom_magnitudes(
        nbody_topology, max_angular_momentum
    )
    spin_magnitude_domain = __get_spin_magnitudes(nbody_topology, max_spin_magnitude)
    if "helicity" in formalism:
        formalism_node_settings.conservation_rules = {
            spin_magnitude_conservation,
            helicity_conservation,
        }
        formalism_node_settings.qn_domains = {
            NodeQN.l_magnitude: angular_momentum_domain,
            NodeQN.s_magnitude: spin_magnitude_domain,
        }
    elif formalism == "canonical":
        formalism_node_settings.conservation_rules = {spin_magnitude_conservation}
        if nbody_topology:
            formalism_node_settings.conservation_rules = {
                spin_conservation,
                ls_spin_validity,
            }
        formalism_node_settings.qn_domains = {
            NodeQN.l_magnitude: angular_momentum_domain,
            NodeQN.l_projection: __extend_negative(angular_momentum_domain),
            NodeQN.s_magnitude: spin_magnitude_domain,
            NodeQN.s_projection: __extend_negative(spin_magnitude_domain),
        }
    if formalism == "canonical-helicity":
        formalism_node_settings.conservation_rules.update({
            clebsch_gordan_helicity_to_canonical,
            ls_spin_validity,
        })
        formalism_node_settings.qn_domains.update({
            NodeQN.l_projection: [0],
            NodeQN.s_projection: __extend_negative(spin_magnitude_domain),
        })
    if mass_conservation_factor is not None:
        formalism_node_settings.conservation_rules.add(
            MassConservation(mass_conservation_factor)
        )

    interaction_type_settings = {}
    weak_node_settings = deepcopy(formalism_node_settings)
    weak_node_settings.conservation_rules.update([
        ChargeConservation(),  # type: ignore[abstract]
        ElectronLNConservation(),  # type: ignore[abstract]
        MuonLNConservation(),  # type: ignore[abstract]
        TauLNConservation(),  # type: ignore[abstract]
        BaryonNumberConservation(),  # type: ignore[abstract]
        identical_particle_symmetrization,
    ])
    weak_node_settings.interaction_strength = 10 ** (-4)
    weak_edge_settings = deepcopy(formalism_edge_settings)

    interaction_type_settings[InteractionType.WEAK] = (
        weak_edge_settings,
        weak_node_settings,
    )

    em_node_settings = deepcopy(weak_node_settings)
    em_node_settings.conservation_rules.update({
        CharmConservation(),  # type: ignore[abstract]
        StrangenessConservation(),  # type: ignore[abstract]
        BottomnessConservation(),  # type: ignore[abstract]
        parity_conservation,
        c_parity_conservation,
    })
    if "helicity" in formalism:
        em_node_settings.conservation_rules.add(parity_conservation_helicity)
        em_node_settings.qn_domains.update({NodeQN.parity_prefactor: [-1, 1]})

    em_node_settings.interaction_strength = 1
    em_edge_settings = deepcopy(weak_edge_settings)
    interaction_type_settings[InteractionType.EM] = (
        em_edge_settings,
        em_node_settings,
    )

    strong_node_settings = deepcopy(em_node_settings)
    strong_node_settings.conservation_rules.update({
        isospin_conservation,
        g_parity_conservation,
    })

    strong_node_settings.interaction_strength = 60
    strong_edge_settings = deepcopy(em_edge_settings)
    interaction_type_settings[InteractionType.STRONG] = (
        strong_edge_settings,
        strong_node_settings,
    )

    return interaction_type_settings


def __get_ang_mom_magnitudes(is_nbody: bool, max_angular_momentum: int) -> list[int]:
    if is_nbody:
        return [0]
    return _int_domain(0, max_angular_momentum)  # type: ignore[return-value]


def __get_spin_magnitudes(is_nbody: bool, max_spin_magnitude: float) -> list[Fraction]:
    if is_nbody:
        return [Fraction(0)]
    return _halves_domain(0, max_spin_magnitude)


def _create_domains(particle_db: ParticleCollection) -> dict[Any, list]:
    domains: dict[Any, list] = {
        EdgeQN.electron_lepton_number: [-1, 0, +1],
        EdgeQN.muon_lepton_number: [-1, 0, +1],
        EdgeQN.tau_lepton_number: [-1, 0, +1],
        EdgeQN.parity: [-1, +1],
        EdgeQN.c_parity: [-1, +1, None],
        EdgeQN.g_parity: [-1, +1, None],
    }

    for edge_qn, getter in {
        EdgeQN.charge: lambda p: p.charge,
        EdgeQN.baryon_number: lambda p: p.baryon_number,
        EdgeQN.strangeness: lambda p: p.strangeness,
        EdgeQN.charmness: lambda p: p.charmness,
        EdgeQN.bottomness: lambda p: p.bottomness,
    }.items():
        domains[edge_qn] = __extend_negative(__positive_int_domain(particle_db, getter))

    domains[EdgeQN.spin_magnitude] = __positive_halves_domain(
        particle_db, lambda p: p.spin
    )
    domains[EdgeQN.spin_projection] = __extend_negative(domains[EdgeQN.spin_magnitude])
    domains[EdgeQN.isospin_magnitude] = __positive_halves_domain(
        particle_db,
        lambda p: 0 if p.isospin is None else p.isospin.magnitude,
    )
    domains[EdgeQN.isospin_projection] = __extend_negative(
        domains[EdgeQN.isospin_magnitude]
    )
    return domains


class NumberOfThreads:
    __n_cores: int | None = None

    @classmethod
    def get(cls) -> int:
        if cls.__n_cores is None:
            return multiprocessing.cpu_count()
        return cls.__n_cores

    @classmethod
    def set(cls, n_cores: int | None) -> None:
        """Set the number of threads; use `None` for all available cores."""
        if n_cores is not None and not isinstance(n_cores, int):
            msg = (
                "Can only set the number of cores to an integer or to None (meaning all"
                " available cores)"
            )
            raise TypeError(msg)
        cls.__n_cores = n_cores


def __positive_halves_domain(
    particle_db: ParticleCollection, attr_getter: Callable[[Particle], Any]
) -> list[Fraction]:
    values = set(map(attr_getter, particle_db))
    return _halves_domain(0, max(values))


def __positive_int_domain(
    particle_db: ParticleCollection, attr_getter: Callable[[Particle], Any]
) -> list[int]:
    values = set(map(attr_getter, particle_db))
    return _int_domain(0, max(values))


def _halves_domain(start: float, stop: float) -> list[Fraction]:
    start_frac = Fraction(start)
    stop_frac = Fraction(stop)
    if start_frac.denominator not in {1, 2}:
        msg = f"Start value {start} needs to be multiple of 0.5"
        raise ValueError(msg)
    if stop_frac.denominator not in {1, 2}:
        msg = f"Stop value {stop} needs to be multiple of 0.5"
        raise ValueError(msg)
    return list(arange(start_frac, stop_frac + Fraction(1, 4), delta=Fraction(1, 2)))


def _int_domain(start: int, stop: int) -> list[int]:
    return list(range(start, stop + 1))


def __extend_negative(
    magnitudes: Iterable[int | Fraction],
) -> list[int | Fraction]:
    return sorted(list(magnitudes) + [-x for x in magnitudes if x > 0])
