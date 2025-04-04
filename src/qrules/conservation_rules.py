"""Collection of quantum number conservation rules for particle reactions.

This module is the place where the 'expert' defines the rules that verify quantum
numbers of the reaction.

A rule is a function that takes quantum numbers as input and outputs a boolean. There
are three different types of rules:

1. `GraphElementRule` that work on individual graph edges or nodes.
2. `EdgeQNConservationRule` that work on the interaction level, which use ingoing edges,
   outgoing edges as arguments.  E.g.: `.ChargeConservation`.
3. `ConservationRule` that work on the interaction level, which use ingoing edges,
   outgoing edges and a interaction node as arguments. E.g: `.parity_conservation`.

The arguments can be any type of quantum number. However a rule argument resembling
edges only accepts `~.quantum_numbers.EdgeQuantumNumbers`. Similarly arguments that
resemble a node only accept `~.quantum_numbers.NodeQuantumNumbers`. The argument types
do not have to be limited to a single quantum number, but can be a composite (see
`.CParityEdgeInput`).

.. warning::
    Besides the rule logic itself, a rule also has the responsibility of
    stating its run conditions. These run conditions **must** be stated by
    the type annotations of its :code:`__call__` method. The type annotations
    therefore are not just there for *static* type checking: they also
    carry more information about the rule that is extracted *dynamically*
    by the :mod:`.solving` module.

Generally, the conditions can be separated into two categories:

* variable conditions
* toplogical conditions

Currently, only variable conditions are being used. Topological conditions could be
created in the form of `~typing.Tuple` instead of `~typing.List`.

For additive quantum numbers, the decorator `additive_quantum_number_rule` can be used
to automatically generate the appropriate behavior.


The module is therefore strongly typed (both for the reader of the code and for type
checking with :doc:`mypy <mypy:index>`). An example is `.HelicityParityEdgeInput`, which
has been defined to provide type checks on `.parity_conservation_helicity`.

.. seealso:: :doc:`/usage/conservation`
"""

import operator
from copy import deepcopy
from fractions import Fraction
from functools import reduce
from textwrap import dedent
from typing import Any, Callable, Optional, Protocol, Union

from attrs import define, field, frozen
from attrs.converters import optional

from qrules.quantum_numbers import EdgeQuantumNumbers as EdgeQN
from qrules.quantum_numbers import NodeQuantumNumbers as NodeQN
from qrules.quantum_numbers import arange


def _is_boson(spin_magnitude: Fraction) -> bool:
    return abs(spin_magnitude % 1) < 0.01


def _is_particle_antiparticle_pair(pid1: int, pid2: int) -> bool:
    # we just check if the pid is opposite in sign
    # this is a requirement of the pid numbers of course
    return pid1 == -pid2


class GraphElementRule(Protocol):
    def __call__(self, qns: Any, /) -> bool: ...


class EdgeQNConservationRule(Protocol):
    def __call__(
        self, ingoing_edge_qns: list[Any], outgoing_edge_qns: list[Any], /
    ) -> bool: ...


class ConservationRule(Protocol):
    def __call__(
        self,
        ingoing_edge_qns: list[Any],
        outgoing_edge_qns: list[Any],
        node_qns: Any,
        /,
    ) -> bool: ...


# Note a generic would be more fitting here. However the type annotations of
# __call__ method in a concrete version of the generic are still containing the
# TypeVar types. See https://github.com/python/typing/issues/762
def additive_quantum_number_rule(
    quantum_number: type,
) -> Callable[[Any], EdgeQNConservationRule]:
    r"""Class decorator for creating an additive conservation rule.

    Use this decorator to create a `EdgeQNConservationRule` for a quantum number to
    which an additive conservation rule applies:

    .. math:: \sum q_{in} = \sum q_{out}

    Args:
        quantum_number: Quantum number to which you want to apply the additive
            conservation check. An example would be `.EdgeQuantumNumbers.charge`.
    """

    def decorator(rule_class: Any) -> EdgeQNConservationRule:
        def new_call(
            self: type[EdgeQNConservationRule],  # noqa: ARG001
            ingoing_edge_qns: list[quantum_number],  # type: ignore[valid-type]
            outgoing_edge_qns: list[quantum_number],  # type: ignore[valid-type]
        ) -> bool:
            return sum(ingoing_edge_qns) == sum(outgoing_edge_qns)

        rule_class.__call__ = new_call
        rule_class.__doc__ = dedent(
            f"""
            Decorated via `{additive_quantum_number_rule.__name__}`.

            Check for `~.EdgeQuantumNumbers.{quantum_number.__name__}` conservation.
            """
        )
        return rule_class

    return decorator


@additive_quantum_number_rule(EdgeQN.charge)
class ChargeConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.baryon_number)
class BaryonNumberConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.electron_lepton_number)
class ElectronLNConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.muon_lepton_number)
class MuonLNConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.tau_lepton_number)
class TauLNConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.strangeness)
class StrangenessConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.charmness)
class CharmConservation(EdgeQNConservationRule):
    pass


@additive_quantum_number_rule(EdgeQN.bottomness)
class BottomnessConservation(EdgeQNConservationRule):
    pass


def parity_conservation(
    ingoing_edge_qns: list[EdgeQN.parity],
    outgoing_edge_qns: list[EdgeQN.parity],
    l_magnitude: NodeQN.l_magnitude,
) -> bool:
    r"""Implement :math:`P_{in} = P_{out} \cdot (-1)^L`."""
    if any(p is None for p in [*ingoing_edge_qns, *outgoing_edge_qns]):
        return False
    if len(ingoing_edge_qns) == 1 and len(outgoing_edge_qns) == 2:
        parity_in = reduce(lambda x, y: x * y.value, ingoing_edge_qns, 1)
        parity_out = reduce(lambda x, y: x * y.value, outgoing_edge_qns, 1)
        return parity_in == (parity_out * (-1) ** l_magnitude)
    return True


@frozen
class HelicityParityEdgeInput:
    parity: EdgeQN.parity = field(converter=EdgeQN.parity)
    spin_magnitude: EdgeQN.spin_magnitude = field(converter=EdgeQN.spin_magnitude)
    spin_projection: EdgeQN.spin_projection = field(converter=EdgeQN.spin_projection)


def parity_conservation_helicity(
    ingoing_edge_qns: list[HelicityParityEdgeInput],
    outgoing_edge_qns: list[HelicityParityEdgeInput],
    parity_prefactor: NodeQN.parity_prefactor,
) -> bool:
    r"""Implements parity conservation for helicity formalism.

    Check the following:

    .. math:: A_{-\lambda_1-\lambda_2} = P_1 P_2 P_3 (-1)^{S_2+S_3-S_1}
        A_{\lambda_1\lambda_2}

    .. math:: \mathrm{parity\,prefactor} = P_1 P_2 P_3 (-1)^{S_2+S_3-S_1}

    .. note:: Only the special case :math:`\lambda_1=\lambda_2=0` may return `False`
        independent on the parity prefactor.
    """
    if len(ingoing_edge_qns) == 1 and len(outgoing_edge_qns) == 2:
        out_spins = [x.spin_magnitude for x in outgoing_edge_qns]
        parity_product = reduce(
            lambda x, y: x * y.parity.value if y.parity else x,
            ingoing_edge_qns + outgoing_edge_qns,
            1,
        )

        prefactor = parity_product * (-1.0) ** (
            sum(out_spins) - ingoing_edge_qns[0].spin_magnitude
        )

        if all(x.spin_projection == 0.0 for x in outgoing_edge_qns) and prefactor == -1:
            return False

        return prefactor == parity_prefactor
    return True


@frozen
class CParityEdgeInput:
    spin_magnitude: EdgeQN.spin_magnitude = field(converter=EdgeQN.spin_magnitude)
    pid: EdgeQN.pid = field(converter=EdgeQN.pid)
    c_parity: Optional[EdgeQN.c_parity] = field(converter=EdgeQN.c_parity, default=None)


@frozen
class CParityNodeInput:
    # These converters currently do not do anything, as "NewType"s do not have constructors
    l_magnitude: NodeQN.l_magnitude = field(converter=NodeQN.l_magnitude)
    s_magnitude: NodeQN.s_magnitude = field(converter=NodeQN.s_magnitude)


def c_parity_conservation(
    ingoing_edge_qns: list[CParityEdgeInput],
    outgoing_edge_qns: list[CParityEdgeInput],
    interaction_node_qns: CParityNodeInput,
) -> bool:
    """Check for :math:`C`-parity conservation.

    Implements :math:`C_{in} = C_{out}`.
    """

    def _get_c_parity_multiparticle(
        part_qns: list[CParityEdgeInput], interaction_qns: CParityNodeInput
    ) -> Optional[int]:
        c_parities_part = [x.c_parity.value for x in part_qns if x.c_parity]
        # if all states have C parity defined, then just multiply them
        if len(c_parities_part) == len(part_qns):
            return reduce(operator.mul, c_parities_part, 1)

        # two particle case
        if len(part_qns) == 2:  # noqa: SIM102
            if _is_particle_antiparticle_pair(part_qns[0].pid, part_qns[1].pid):
                ang_mom = interaction_qns.l_magnitude
                # if boson
                if _is_boson(part_qns[0].spin_magnitude):
                    return (-1) ** int(ang_mom)
                coupled_spin = Fraction(interaction_qns.s_magnitude)
                if isinstance(coupled_spin, int) or coupled_spin.denominator == 1:
                    return (-1) ** int(ang_mom + coupled_spin)
        return None

    c_parity_in = _get_c_parity_multiparticle(ingoing_edge_qns, interaction_node_qns)
    if c_parity_in is None:
        return True

    c_parity_out = _get_c_parity_multiparticle(outgoing_edge_qns, interaction_node_qns)
    if c_parity_out is None:
        return True

    return c_parity_in == c_parity_out


@frozen
class GParityEdgeInput:
    isospin_magnitude: EdgeQN.isospin_magnitude = field(
        converter=EdgeQN.isospin_magnitude
    )
    spin_magnitude: EdgeQN.spin_magnitude = field(converter=EdgeQN.spin_magnitude)
    pid: EdgeQN.pid = field(converter=EdgeQN.pid)
    g_parity: Optional[EdgeQN.g_parity] = field(converter=EdgeQN.g_parity, default=None)


@frozen
class GParityNodeInput:
    l_magnitude: NodeQN.l_magnitude = field(converter=NodeQN.l_magnitude)
    s_magnitude: NodeQN.s_magnitude = field(converter=NodeQN.s_magnitude)


def g_parity_conservation(  # noqa: C901
    ingoing_edge_qns: list[GParityEdgeInput],
    outgoing_edge_qns: list[GParityEdgeInput],
    interaction_qns: GParityNodeInput,
) -> bool:
    """Check for :math:`G`-parity conservation.

    Implements for :math:`G_{in} = G_{out}`.
    """

    def check_multistate_g_parity(
        isospin: EdgeQN.isospin_magnitude,
        double_state_qns: tuple[GParityEdgeInput, GParityEdgeInput],
    ) -> Optional[int]:
        if _is_particle_antiparticle_pair(
            double_state_qns[0].pid, double_state_qns[1].pid
        ):
            ang_mom = interaction_qns.l_magnitude
            if isinstance(isospin, int) or isospin.denominator == 1:
                # if boson
                if _is_boson(double_state_qns[0].spin_magnitude):
                    return (-1) ** int(ang_mom + isospin)
                coupled_spin = interaction_qns.s_magnitude
                if isinstance(coupled_spin, int) or coupled_spin.denominator == 1:
                    return (-1) ** int(ang_mom + coupled_spin + isospin)
        return None

    def check_g_parity_isobar(
        single_state: GParityEdgeInput,
        couple_state: tuple[GParityEdgeInput, GParityEdgeInput],
    ) -> bool:
        couple_state_g_parity = check_multistate_g_parity(
            single_state.isospin_magnitude,
            (couple_state[0], couple_state[1]),
        )
        single_state_g_parity = (
            ingoing_edge_qns[0].g_parity.value if ingoing_edge_qns[0].g_parity else None
        )

        if not couple_state_g_parity or not single_state_g_parity:
            return True
        return couple_state_g_parity == single_state_g_parity

    no_g_parity_in_part = [True for x in ingoing_edge_qns if x.g_parity is None]
    no_g_parity_out_part = [True for x in outgoing_edge_qns if x.g_parity is None]
    # if all states have G parity defined, then just multiply them
    if not any(no_g_parity_in_part + no_g_parity_out_part):
        in_g_parity = reduce(
            lambda x, y: x * y.g_parity.value if y.g_parity else x,
            ingoing_edge_qns,
            1,
        )
        out_g_parity = reduce(
            lambda x, y: x * y.g_parity.value if y.g_parity else x,
            outgoing_edge_qns,
            1,
        )
        return in_g_parity == out_g_parity

    # two particle case
    particle_counts = (len(ingoing_edge_qns), len(outgoing_edge_qns))
    if particle_counts == (1, 2):
        return check_g_parity_isobar(
            ingoing_edge_qns[0],
            (outgoing_edge_qns[0], outgoing_edge_qns[1]),
        )

    if particle_counts == (2, 1):
        return check_g_parity_isobar(
            outgoing_edge_qns[0],
            (ingoing_edge_qns[0], ingoing_edge_qns[1]),
        )
    return True


@frozen
class IdenticalParticleSymmetryOutEdgeInput:
    spin_magnitude: EdgeQN.spin_magnitude = field(converter=EdgeQN.spin_magnitude)
    spin_projection: EdgeQN.spin_projection = field(converter=EdgeQN.spin_projection)
    pid: EdgeQN.pid = field(converter=EdgeQN.pid)


def identical_particle_symmetrization(
    ingoing_parities: list[EdgeQN.parity],
    outgoing_edge_qns: list[IdenticalParticleSymmetryOutEdgeInput],
) -> bool:
    """Verifies multi particle state symmetrization for identical particles.

    In case of a multi particle state with identical particles, their exchange symmetry
    has to follow the spin statistic theorem.

    For bosonic systems the total exchange symmetry (parity) has to be even (+1). For
    fermionic systems the total exchange symmetry (parity) has to be odd (-1).

    In case of a particle decaying into N identical particles (N>1), the decaying
    particle has to have the same parity as required by the spin statistic theorem of
    the multi body state.
    """

    def _check_particles_identical(
        particles: list[IdenticalParticleSymmetryOutEdgeInput],
    ) -> bool:
        """Check if pids and spins match."""
        if len(particles) == 1:
            return False

        reference_pid = particles[0].pid
        reference_spin_proj = particles[0].spin_projection
        for particle in particles[1:]:
            if particle.pid != reference_pid:
                return False
            if particle.spin_projection != reference_spin_proj:
                return False
        return True

    if len(ingoing_parities) == 1 and _check_particles_identical(outgoing_edge_qns):
        if _is_boson(outgoing_edge_qns[0].spin_magnitude):
            # we have a boson, check if parity of mother is even
            parity = ingoing_parities[0]
            if parity == -1:
                # if its odd then return False
                return False
        else:
            # its fermion
            parity = ingoing_parities[0]
            if parity == 1:
                return False

    return True


@frozen
class _Spin:
    magnitude: Union[Fraction, NodeQN.s_magnitude, NodeQN.l_magnitude]
    projection: Union[Fraction, NodeQN.s_projection, NodeQN.l_projection]


def _is_clebsch_gordan_coefficient_zero(
    spin1: _Spin, spin2: _Spin, spin_coupled: _Spin
) -> bool:
    m_1 = spin1.projection
    j_1 = spin1.magnitude
    m_2 = spin2.projection
    j_2 = spin2.magnitude
    proj = spin_coupled.projection
    mag = spin_coupled.magnitude
    if ((j_1 == j_2 and m_1 == m_2) or (m_1 == 0.0 and m_2 == 0.0)) and abs(
        mag - j_1 - j_2
    ) % 2 == 1:
        return True
    if j_1 == mag and m_1 == -proj and abs(j_2 - j_1 - mag) % 2 == 1:
        return True
    return j_2 == mag and m_2 == -proj and abs(j_1 - j_2 - mag) % 2 == 1


@frozen
class SpinNodeInput:
    l_magnitude: NodeQN.l_magnitude = field(converter=NodeQN.l_magnitude)
    l_projection: NodeQN.l_projection = field(converter=NodeQN.l_projection)
    s_magnitude: NodeQN.s_magnitude = field(converter=NodeQN.s_magnitude)
    s_projection: NodeQN.s_projection = field(converter=NodeQN.s_projection)


@frozen
class SpinMagnitudeNodeInput:
    l_magnitude: NodeQN.l_magnitude = field(converter=NodeQN.l_magnitude)
    s_magnitude: NodeQN.s_magnitude = field(converter=NodeQN.s_magnitude)


def ls_spin_validity(spin_input: SpinNodeInput) -> bool:
    r"""Check for valid isospin magnitude and projection."""
    return _check_spin_valid(
        spin_input.l_magnitude, spin_input.l_projection
    ) and _check_spin_valid(spin_input.s_magnitude, spin_input.s_projection)


def _check_magnitude(
    in_part: list[Fraction],
    out_part: list[Fraction],
    interaction_qns: Optional[Union[SpinMagnitudeNodeInput, SpinNodeInput]],
) -> bool:
    def couple_mags(j_1: Fraction, j_2: Fraction) -> list[Fraction]:
        return [
            Fraction(x, 2)
            for x in range(int(2 * abs(j_1 - j_2)), int(2 * (j_1 + j_2 + 1)), 2)
        ]

    def couple_magnitudes(
        magnitudes: list[Fraction],
        interaction_qns: Optional[Union[SpinMagnitudeNodeInput, SpinNodeInput]],
    ) -> set[Fraction]:
        if len(magnitudes) == 1:
            return set(magnitudes)

        coupled_magnitudes = {magnitudes[0]}
        for mag in magnitudes[1:]:
            temp_set = coupled_magnitudes
            coupled_magnitudes = set()
            for ref_mag in temp_set:
                coupled_magnitudes.update(couple_mags(mag, ref_mag))

        if interaction_qns:
            if interaction_qns.s_magnitude in coupled_magnitudes:
                return set(
                    couple_mags(
                        interaction_qns.s_magnitude,
                        interaction_qns.l_magnitude,
                    )
                )
            return set()  # in case there the spin coupling fails
        return coupled_magnitudes

    in_tot_spins = couple_magnitudes(in_part, interaction_qns)
    out_tot_spins = couple_magnitudes(out_part, interaction_qns)
    matching_spins = in_tot_spins.intersection(out_tot_spins)

    return len(matching_spins) > 0


def _check_spin_couplings(
    in_part: list[_Spin],
    out_part: list[_Spin],
    interaction_qns: Optional[SpinNodeInput],
) -> bool:
    in_tot_spins = __calculate_total_spins(in_part, interaction_qns)
    out_tot_spins = __calculate_total_spins(out_part, interaction_qns)
    matching_spins = in_tot_spins & out_tot_spins
    return len(matching_spins) > 0


def __calculate_total_spins(
    spins: list[_Spin],
    interaction_qns: Optional[SpinNodeInput] = None,
) -> set[_Spin]:
    total_spins = set()
    if len(spins) == 1:
        return set(spins)
    total_spins = __create_coupled_spins(spins)
    if interaction_qns:
        coupled_spin = _Spin(interaction_qns.s_magnitude, interaction_qns.s_projection)
        if coupled_spin in total_spins:
            return __spin_couplings(
                coupled_spin,
                _Spin(interaction_qns.l_magnitude, interaction_qns.l_projection),
            )
        total_spins = set()

    return total_spins


def __create_coupled_spins(spins: list[_Spin]) -> set[_Spin]:
    """Creates all combinations of coupled spins."""
    spins_daughters_coupled: set[_Spin] = set()
    spin_list = deepcopy(spins)
    while spin_list:
        if spins_daughters_coupled:
            temp_coupled_spins = set()
            tempspin = spin_list.pop()
            for spin in spins_daughters_coupled:
                coupled_spins = __spin_couplings(spin, tempspin)
                temp_coupled_spins.update(coupled_spins)
            spins_daughters_coupled = temp_coupled_spins
        else:
            spins_daughters_coupled.add(spin_list.pop())

    return spins_daughters_coupled


def __spin_couplings(spin1: _Spin, spin2: _Spin) -> set[_Spin]:
    r"""Implement the coupling of two spins.

    :math:`|S_1 - S_2| \leq S \leq |S_1 + S_2|` and :math:`M_1 + M_2 = M`
    """
    sum_proj = spin1.projection + spin2.projection
    return {
        _Spin(Fraction(x), Fraction(sum_proj))
        for x in arange(
            abs(spin1.magnitude - spin2.magnitude),
            spin1.magnitude + spin2.magnitude + 1,
        )
        if x >= abs(sum_proj)
        and not _is_clebsch_gordan_coefficient_zero(spin1, spin2, _Spin(x, sum_proj))
    }


@define
class IsoSpinEdgeInput:
    isospin_magnitude: EdgeQN.isospin_magnitude = field(
        converter=EdgeQN.isospin_magnitude
    )
    isospin_projection: EdgeQN.isospin_projection = field(
        converter=EdgeQN.isospin_projection
    )


def _check_spin_valid(magnitude: Fraction, projection: Fraction) -> bool:
    if magnitude.denominator not in {1, 2}:
        return False
    if abs(projection) > magnitude:
        return False
    return (projection - magnitude).denominator == 1


def isospin_validity(isospin: IsoSpinEdgeInput) -> bool:
    r"""Check for valid isospin magnitude and projection."""
    return _check_spin_valid(isospin.isospin_magnitude, isospin.isospin_projection)


def isospin_conservation(
    ingoing_isospins: list[IsoSpinEdgeInput],
    outgoing_isospins: list[IsoSpinEdgeInput],
) -> bool:
    r"""Check for isospin conservation.

    Implements

    .. math::
        |I_1 - I_2| \leq I \leq |I_1 + I_2|

    Also checks :math:`I_{1,z} + I_{2,z} = I_z` and if Clebsch-Gordan coefficients are
    all 0.
    """
    if sum(x.isospin_projection for x in ingoing_isospins) != sum(
        x.isospin_projection for x in outgoing_isospins
    ):
        return False
    if not all(isospin_validity(x) for x in ingoing_isospins + outgoing_isospins):
        return False
    return _check_spin_couplings(
        [_Spin(x.isospin_magnitude, x.isospin_projection) for x in ingoing_isospins],
        [_Spin(x.isospin_magnitude, x.isospin_projection) for x in outgoing_isospins],
        None,
    )


@define
class SpinEdgeInput:
    spin_magnitude: EdgeQN.spin_magnitude = field(converter=EdgeQN.spin_magnitude)
    spin_projection: EdgeQN.spin_projection = field(converter=EdgeQN.spin_projection)


def spin_validity(spin: SpinEdgeInput) -> bool:
    r"""Check for valid spin magnitude and projection."""
    return _check_spin_valid(spin.spin_magnitude, spin.spin_projection)


def spin_conservation(
    ingoing_spins: list[SpinEdgeInput],
    outgoing_spins: list[SpinEdgeInput],
    interaction_qns: SpinNodeInput,
) -> bool:
    r"""Check for spin conservation.

    Implements

    .. math::
        |S_1 - S_2| \leq S \leq |S_1 + S_2|

    and

    .. math::
        |L - S| \leq J \leq |L + S|

    Also checks :math:`M_1 + M_2 = M` and if Clebsch-Gordan coefficients are all 0.

    .. seealso:: /docs/usage/ls-coupling
    """
    # L and S can only be used if one side is a single state
    # and the other side contains of two states (isobar)
    # So do a full check if this is the case
    if (len(ingoing_spins) == 1 and len(outgoing_spins) == 2) or (
        len(ingoing_spins) == 2 and len(outgoing_spins) == 1
    ):
        return _check_spin_couplings(
            [_Spin(x.spin_magnitude, x.spin_projection) for x in ingoing_spins],
            [_Spin(x.spin_magnitude, x.spin_projection) for x in outgoing_spins],
            interaction_qns,
        )

    # otherwise don't use S and L and just check magnitude
    # are integral or non integral on both sides
    return (
        sum(float(x.spin_magnitude) for x in ingoing_spins).is_integer()  # type: ignore[union-attr]
        == sum(float(x.spin_magnitude) for x in outgoing_spins).is_integer()  # type: ignore[union-attr]
    )


def spin_magnitude_conservation(
    ingoing_spin_magnitudes: list[EdgeQN.spin_magnitude],
    outgoing_spin_magnitudes: list[EdgeQN.spin_magnitude],
    interaction_qns: SpinMagnitudeNodeInput,
) -> bool:
    r"""Check for spin conservation.

    Implements

    .. math::
        |S_1 - S_2| \leq S \leq |S_1 + S_2|

    and

    .. math::
        |L - S| \leq J \leq |L + S|
    """
    # L and S can only be used if one side is a single state
    # and the other side contains of two states (isobar)
    # So do a full check if this is the case
    if (len(ingoing_spin_magnitudes) == 1 and len(outgoing_spin_magnitudes) == 2) or (
        len(ingoing_spin_magnitudes) == 2 and len(outgoing_spin_magnitudes) == 1
    ):
        return _check_magnitude(
            [Fraction(x) for x in ingoing_spin_magnitudes],
            [Fraction(x) for x in outgoing_spin_magnitudes],
            interaction_qns,
        )

    # otherwise don't use S and L and just check magnitude
    # are integral or non integral on both sides
    return (
        sum(float(x) for x in ingoing_spin_magnitudes).is_integer()  # type: ignore[union-attr]
        == sum(float(x) for x in outgoing_spin_magnitudes).is_integer()  # type: ignore[union-attr]
    )


def clebsch_gordan_helicity_to_canonical(
    ingoing_spins: list[SpinEdgeInput],
    outgoing_spins: list[SpinEdgeInput],
    interaction_qns: SpinNodeInput,
) -> bool:
    """Implement Clebsch-Gordan checks.

    For :math:`S_1, S_2` to :math:`S` and the :math:`L,S` to :math:`J` coupling based on
    the conversion of helicity to canonical amplitude sums.

    .. note:: This rule does not check that the spin magnitudes couple correctly to
        :math:`L` and :math:`S`, as this is already performed by
        `.spin_magnitude_conservation`.
    """
    if len(ingoing_spins) == 1 and len(outgoing_spins) == 2:
        out_spin1 = _Spin(
            outgoing_spins[0].spin_magnitude,
            outgoing_spins[0].spin_projection,
        )
        out_spin2 = _Spin(
            outgoing_spins[1].spin_magnitude,
            -outgoing_spins[1].spin_projection,
        )

        helicity_diff = out_spin1.projection + out_spin2.projection
        if helicity_diff != interaction_qns.s_projection:
            return False

        ang_mom = _Spin(interaction_qns.l_magnitude, interaction_qns.l_projection)
        coupled_spin = _Spin(interaction_qns.s_magnitude, interaction_qns.s_projection)
        parent_spin = ingoing_spins[0].spin_magnitude

        coupled_spin = _Spin(coupled_spin.magnitude, helicity_diff)
        if not _check_spin_valid(coupled_spin.magnitude, coupled_spin.projection):
            return False
        in_spin = _Spin(parent_spin, helicity_diff)
        if not _check_spin_valid(in_spin.magnitude, in_spin.projection):
            return False

        if _is_clebsch_gordan_coefficient_zero(out_spin1, out_spin2, coupled_spin):
            return False

        return not _is_clebsch_gordan_coefficient_zero(ang_mom, coupled_spin, in_spin)
    return False


def helicity_conservation(
    ingoing_spin_mags: list[EdgeQN.spin_magnitude],
    outgoing_helicities: list[EdgeQN.spin_projection],
) -> bool:
    r"""Implementation of helicity conservation.

    Check for :math:`|\lambda_2-\lambda_3| \leq S_1`.
    """
    if len(ingoing_spin_mags) == 1 and len(outgoing_helicities) == 2:
        mother_spin = ingoing_spin_mags[0]
        if mother_spin >= abs(outgoing_helicities[0] - outgoing_helicities[1]):
            return True
    return False


@frozen
class GellMannNishijimaInput:
    charge: EdgeQN.charge = field(converter=EdgeQN.charge)
    isospin_projection: Optional[EdgeQN.isospin_projection] = field(
        converter=optional(EdgeQN.isospin_projection), default=None
    )
    strangeness: Optional[EdgeQN.strangeness] = field(
        converter=optional(EdgeQN.strangeness), default=None
    )
    charmness: Optional[EdgeQN.charmness] = field(
        converter=optional(EdgeQN.charmness), default=None
    )
    bottomness: Optional[EdgeQN.bottomness] = field(
        converter=optional(EdgeQN.bottomness), default=None
    )
    topness: Optional[EdgeQN.topness] = field(
        converter=optional(EdgeQN.topness), default=None
    )
    baryon_number: Optional[EdgeQN.baryon_number] = field(
        converter=optional(EdgeQN.baryon_number), default=None
    )
    electron_lepton_number: Optional[EdgeQN.electron_lepton_number] = field(
        converter=optional(EdgeQN.electron_lepton_number), default=None
    )
    muon_lepton_number: Optional[EdgeQN.muon_lepton_number] = field(
        converter=optional(EdgeQN.muon_lepton_number), default=None
    )
    tau_lepton_number: Optional[EdgeQN.tau_lepton_number] = field(
        converter=optional(EdgeQN.tau_lepton_number), default=None
    )


def gellmann_nishijima(edge_qns: GellMannNishijimaInput) -> bool:
    r"""Check the Gell-Mann-Nishijima formula.

    `Gell-Mann-Nishijima formula
    <https://en.wikipedia.org/wiki/Gell-Mann%E2%80%93Nishijima_formula>`_:

    .. math::
        Q = I_3 + \frac{1}{2}(B+S+C+B'+T)

    where
    :math:`Q` is charge (computed),
    :math:`I_3` is `.Spin.projection` of `~.Particle.isospin`,
    :math:`B` is `~.Particle.baryon_number`,
    :math:`S` is `~.Particle.strangeness`,
    :math:`C` is `~.Particle.charmness`,
    :math:`B'` is `~.Particle.bottomness`, and
    :math:`T` is `~.Particle.topness`.
    """

    def calculate_hypercharge(
        particle: GellMannNishijimaInput,
    ) -> float:
        """Calculate the hypercharge :math:`Y=S+C+B+T+B`."""
        return sum(
            0.0 if x is None else x
            for x in [
                particle.strangeness,
                particle.charmness,
                particle.bottomness,
                particle.topness,
                particle.baryon_number,
            ]
        )

    if (
        edge_qns.electron_lepton_number
        or edge_qns.muon_lepton_number
        or edge_qns.tau_lepton_number
    ):
        return True
    isospin_3 = Fraction(0)
    if edge_qns.isospin_projection:
        isospin_3 = edge_qns.isospin_projection
    return float(edge_qns.charge) == isospin_3 + 0.5 * calculate_hypercharge(edge_qns)


@frozen
class MassEdgeInput:
    mass: EdgeQN.mass = field(converter=EdgeQN.mass)
    width: Optional[EdgeQN.width] = field(converter=EdgeQN.width, default=None)


class MassConservation:
    """Mass conservation rule."""

    def __init__(self, width_factor: float) -> None:
        self.__width_factor = width_factor

    def __call__(
        self,
        ingoing_edge_qns: list[MassEdgeInput],
        outgoing_edge_qns: list[MassEdgeInput],
    ) -> bool:
        r"""Implements mass conservation.

        :math:`M_{out} - N \cdot W_{out} < M_{in} + N \cdot W_{in}`

        It makes sure that the net mass outgoing state :math:`M_{out}` is smaller than
        the net mass of the ingoing state :math:`M_{in}`. Also the width :math:`W` of
        the states is taken into account.
        """
        mass_in = sum(x.mass for x in ingoing_edge_qns)
        width_in = sum(x.width for x in ingoing_edge_qns if x.width)
        mass_out = sum(x.mass for x in outgoing_edge_qns)
        width_out = sum(x.width for x in outgoing_edge_qns if x.width)

        return (mass_out - self.__width_factor * width_out) < (
            mass_in + self.__width_factor * width_in
        )
