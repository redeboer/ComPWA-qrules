from fractions import Fraction
from textwrap import dedent

import pydot
import pytest

import qrules
from qrules import io
from qrules.io._dot import (
    _collapse_graphs,
    _get_particle_graphs,
    _strip_projections,
    as_string,
)
from qrules.particle import Particle, ParticleCollection
from qrules.settings import InteractionType
from qrules.solving import QNProblemSet, QNResult
from qrules.topology import (
    Edge,
    Topology,
    create_isobar_topologies,
    create_n_body_topology,
)
from qrules.transition import (
    ProblemSet,
    ReactionInfo,
    SpinFormalism,
    StateTransitionManager,
)


def test_asdot(reaction: ReactionInfo):
    for transition in reaction.transitions:
        dot_data = io.asdot(transition)
        assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(reaction)
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(reaction, strip_spin=True)
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(reaction, collapse_graphs=True)
    assert pydot.graph_from_dot_data(dot_data) is not None


def test_asdot_exact_format(reaction: ReactionInfo):
    dot = io.asdot(reaction.transitions[0], render_node=True)
    if reaction.formalism == "helicity":
        expected_dot = """
digraph {
    rankdir=LR
    node [shape=none, width=0]
    edge [arrowhead=none]
    bgcolor=none
    0 [label="0: gamma[-1]"]
    1 [label="1: pi0[0]"]
    2 [label="2: pi0[0]"]
    A [label="J/psi(1S)[-1]"]
    { rank=same A }
    { rank=same 0, 1, 2 }
    A -> N0
    N0 -> N1 [label="f(0)(980)[0]"]
    N0 -> 0
    N1 -> 1
    N1 -> 2
    N0 [label="P=+1"]
    N1 [label="P=+1"]
}
        """
    else:
        expected_dot = """
digraph {
    rankdir=LR
    node [shape=none, width=0]
    edge [arrowhead=none]
    bgcolor=none
    0 [label="0: gamma[-1]"]
    1 [label="1: pi0[0]"]
    2 [label="2: pi0[0]"]
    A [label="J/psi(1S)[-1]"]
    { rank=same A }
    { rank=same 0, 1, 2 }
    A -> N0
    N0 -> N1 [label="f(0)(980)[0]"]
    N0 -> 0
    N1 -> 1
    N1 -> 2
    N0 [label="L=|0,0⟩\nS=|1,-1⟩\nP=+1"]
    N1 [label="L=|0,0⟩\nS=|0,0⟩\nP=+1"]
}
        """
    assert dot.strip() == expected_dot.strip()


def test_asdot_graphviz_attrs(reaction: ReactionInfo):
    dot_data = io.asdot(reaction, size=12)
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(reaction, bgcolor="red", size=12)
    assert pydot.graph_from_dot_data(dot_data) is not None
    assert '\n    bgcolor="red"\n' in dot_data
    assert "\n    size=12\n" in dot_data
    assert "bgcolor=none" not in dot_data


def test_asdot_qn_problem_set(qn_problem_and_result: tuple[QNProblemSet, QNResult]):
    qn_problem_set, _ = qn_problem_and_result
    dot_data = qrules.io.asdot(qn_problem_set, render_node=True)
    assert pydot.graph_from_dot_data(dot_data) is not None


def test_asdot_with_styled_edges_and_nodes(reaction: ReactionInfo, output_dir):
    transition = reaction.transitions[0]
    dot = io.asdot(
        transition,
        edge_style={"fontcolor": "blue"},
        node_style={"fontcolor": "darkgreen", "shape": "ellipse"},
    )
    assert pydot.graph_from_dot_data(dot) is not None
    with open(output_dir + f"styled_{reaction.formalism}.gv", "w") as stream:
        stream.write(dot)
    assert '0 [fontcolor="blue", label="0: gamma[-1]"]' in dot
    assert 'N0 -> N1 [fontcolor="blue", label="f(0)(980)[0]"]' in dot
    assert 'N0 [fontcolor="darkgreen", shape="ellipse", label=""]' in dot


def test_asdot_no_label_overwriting(reaction: ReactionInfo):
    transition = reaction.transitions[0]
    label = "should be ignored"
    dot_data = io.asdot(
        transition,
        edge_style={"label": label},
        node_style={"label": label},
    )
    assert pydot.graph_from_dot_data(dot_data) is not None
    assert label not in dot_data


@pytest.mark.parametrize(
    "formalism",
    ["canonical", "canonical-helicity", "helicity"],
)
def test_asdot_problemset(formalism: SpinFormalism):
    stm = StateTransitionManager(
        initial_state=[("J/psi(1S)", [+1])],
        final_state=["gamma", "pi0", "pi0"],
        formalism=formalism,
    )
    problem_sets = stm.create_problem_sets()
    for problem_set_list in problem_sets.values():
        for problem_set in problem_set_list:
            dot_data = io.asdot(problem_set)
            assert pydot.graph_from_dot_data(dot_data) is not None
            topology = problem_set.topology
            initial_facts = problem_set.initial_facts
            settings = problem_set.solving_settings
            dot_data = io.asdot([(topology, initial_facts)])
            assert pydot.graph_from_dot_data(dot_data) is not None
            dot_data = io.asdot([(topology, settings)])
            assert pydot.graph_from_dot_data(dot_data) is not None
        dot_data = io.asdot(problem_set_list)
        assert pydot.graph_from_dot_data(dot_data) is not None


def test_asdot_topology():
    dot_data = io.asdot(create_n_body_topology(3, 4))
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(create_isobar_topologies(2))
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(create_isobar_topologies(3))
    assert pydot.graph_from_dot_data(dot_data) is not None
    dot_data = io.asdot(create_isobar_topologies(4))
    assert pydot.graph_from_dot_data(dot_data) is not None


def test_as_string_dict(
    problem_sets: dict[float, list[ProblemSet]],
    qn_problem_and_result: tuple[QNProblemSet, QNResult],
):
    _, qn_result = qn_problem_and_result
    problem_set = problem_sets[3600.0][0]
    interaction = qn_result.solutions[1].interactions[1]
    intermediate_state, *_ = qn_result.solutions[0].intermediate_states.values()
    node_setting = problem_set.solving_settings.interactions[0]
    intermediate_setting, *_ = problem_set.solving_settings.intermediate_states.values()

    dot = as_string(intermediate_setting).strip()
    expected_dot = dedent("""
        RULES
        spin_validity - 62
        isospin_validity - 61
        gellmann_nishijima - 50
        DOMAINS
        baryon_number ∊ [-1, +1]
        bottomness ∊ [0]
        c_parity ∊ [None]
        charge ∊ [-1, 0, +1]
        charmness ∊ [0]
        electron_lepton_number ∊ [0]
        g_parity ∊ [None]
        isospin_magnitude ∊ [1]
        isospin_projection ∊ [-1, 0, +1]
        muon_lepton_number ∊ [0]
        parity ∊ [-1, +1]
        spin_magnitude ∊ [1/2]
        spin_projection ∊ [-4, -7/2, -3, -5/2, -2, -3/2, -1, -1/2, 0, +1/2, +1, +3/2, +2, +5/2, +3, +7/2, +4]
        strangeness ∊ [-1, +1]
        tau_lepton_number ∊ [0]
        topness ∊ [0]
    """).strip()
    assert dot == expected_dot

    dot = as_string(node_setting).strip()
    expected_dot = dedent("""
        RULES
        clebsch_gordan_helicity_to_canonical - NA
        BaryonNumberConservation - 90
        ls_spin_validity - 89
        spin_magnitude_conservation - 8
        CharmConservation - 70
        helicity_conservation - 7
        StrangenessConservation - 69
        BottomnessConservation - 68
        isospin_conservation - 60
        parity_conservation - 6
        c_parity_conservation - 5
        ElectronLNConservation - 45
        MuonLNConservation - 44
        TauLNConservation - 43
        parity_conservation_helicity - 4
        g_parity_conservation - 3
        identical_particle_symmetrization - 2
        ChargeConservation - 100
        MassConservation - 10
        DOMAINS
        l_magnitude ∊ [0, 1]
        l_projection ∊ [0]
        parity_prefactor ∊ [-1, +1]
        s_magnitude ∊ [0, 1/2, 1, 3/2, 2]
        s_projection ∊ [-2, -3/2, -1, -1/2, 0, +1/2, +1, +3/2, +2]
    """).strip()
    assert dot == expected_dot

    dot = as_string(interaction).strip()
    expected_dot = dedent("""
        l_magnitude = 0
        s_magnitude = 1/2
        l_projection = 0
        s_projection = -1/2
        parity_prefactor = +1
    """).strip()
    assert dot == expected_dot

    dot = as_string(intermediate_state).strip()
    expected_dot = dedent("""
        spin_magnitude = 1/2
        spin_projection = +1/2
        parity = +1
        isospin_magnitude = 1
        isospin_projection = -1
        baryon_number = -1
        charge = -1
        strangeness = +1
        pid = -23222
        mass = 1.75
        width = 0.15
    """).strip()
    assert dot == expected_dot


def test_as_string_spin_tuple(particle_database: ParticleCollection):
    # non-spin
    src = as_string(("a", "b", "c"))
    assert src == "a\nb\nc"
    src = as_string(("a", "b"))
    assert src == "a\nb"

    # spin
    src = as_string((2, 1))
    assert src == "|2,+1⟩"

    # particle with spin projection
    pion = particle_database["J/psi(1S)"]
    src = as_string((pion, 1))
    assert src == "J/psi(1S)[+1]"
    src = as_string((pion, Fraction(-1)))
    assert src == "J/psi(1S)[-1]"


class TestWrite:
    def test_write_topology(self, output_dir):
        output_file = output_dir + "two_body_decay_topology.gv"
        topology = Topology(
            nodes={0},
            edges={
                -1: Edge(None, 0),
                0: Edge(0, None),
                1: Edge(0, None),
            },
        )
        io.write(
            instance=topology,
            filename=output_file,
        )
        with open(output_file) as stream:
            dot_data = stream.read()
        assert pydot.graph_from_dot_data(dot_data) is not None

    def test_write_single_graph(self, output_dir: str, reaction: ReactionInfo):
        for i, transition in enumerate(reaction.transitions):
            output_file = output_dir + f"test_single_graph_{i}.gv"
            io.write(
                instance=transition,
                filename=output_file,
            )
            with open(output_file) as stream:
                dot_data = stream.read()
            assert pydot.graph_from_dot_data(dot_data) is not None

    def test_write_graph_list(self, output_dir: str, reaction: ReactionInfo):
        for i, transition in enumerate(reaction.transitions):
            output_file = output_dir + f"test_graph_list_{i}.gv"
            io.write(transition, filename=output_file)
            with open(output_file) as stream:
                dot_data = stream.read()
            assert pydot.graph_from_dot_data(dot_data) is not None

    def test_write_strip_spin(self, output_dir: str, reaction: ReactionInfo):
        output_file = output_dir + "test_particle_graphs.gv"
        io.write(
            instance=io.asdot(reaction, strip_spin=True),
            filename=output_file,
        )
        with open(output_file) as stream:
            dot_data = stream.read()
        assert pydot.graph_from_dot_data(dot_data) is not None


def test_collapse_graphs(
    reaction: ReactionInfo,
    particle_database: ParticleCollection,
):
    pdg = particle_database
    particle_graphs = _get_particle_graphs(reaction.transitions)  # type: ignore[arg-type]
    assert len(particle_graphs) == 2

    collapsed_graphs = _collapse_graphs(reaction.transitions)  # type: ignore[arg-type]
    assert len(collapsed_graphs) == 1
    graph = next(iter(collapsed_graphs))
    edge_id = next(iter(graph.topology.intermediate_edge_ids))
    f_resonances = pdg.filter(lambda p: p.name in {"f(0)(980)", "f(0)(1500)"})
    intermediate_states = graph.states[edge_id]
    assert isinstance(intermediate_states, tuple)
    assert all(isinstance(i, Particle) for i in intermediate_states)
    assert intermediate_states == f_resonances


def test_get_particle_graphs(
    reaction: ReactionInfo, particle_database: ParticleCollection
):
    pdg = particle_database
    graphs = _get_particle_graphs(reaction.transitions)  # type: ignore[arg-type]
    assert len(graphs) == 2
    assert graphs[0].states[3] == pdg["f(0)(980)"]
    assert graphs[1].states[3] == pdg["f(0)(1500)"]
    assert len(graphs[0].topology.edges) == 5
    for i in range(-1, 3):
        assert graphs[0].states[i] is graphs[1].states[i]


def test_strip_projections(skh_particle_version: str):
    assert skh_particle_version is not None  # skips test if particle version too low
    resonance = "Sigma(1670)~-"
    reaction = qrules.generate_transitions(
        initial_state=[("J/psi(1S)", [+1])],
        final_state=["K0", ("Sigma+", [+0.5]), ("p~", [+0.5])],
        allowed_intermediate_particles=[resonance],
        allowed_interaction_types="strong",
    )

    assert len(reaction.transitions) == 5
    transition = reaction.transitions[0]

    assert transition.intermediate_states[3].particle.name == resonance
    assert transition.intermediate_states[3].spin_projection == -0.5
    assert len(transition.interactions) == 2
    assert transition.interactions[0].s_projection == 1
    assert transition.interactions[0].l_projection == 0
    assert transition.interactions[1].s_projection == -0.5
    assert transition.interactions[1].l_projection == 0

    stripped_transition = _strip_projections(transition)  # type: ignore[arg-type]
    assert stripped_transition.states[3].name == resonance
    assert stripped_transition.interactions[0].s_projection is None
    assert stripped_transition.interactions[0].l_projection is None
    assert stripped_transition.interactions[1].s_projection is None
    assert stripped_transition.interactions[1].l_projection is None


@pytest.fixture
def stm() -> StateTransitionManager:
    stm = StateTransitionManager(
        initial_state=[("J/psi(1S)", [+1])],
        final_state=["K0", ("Sigma+", [+0.5]), ("p~", [+0.5])],
        allowed_intermediate_particles=["Sigma(1750)"],
        formalism="canonical-helicity",
    )
    stm.set_allowed_interaction_types([InteractionType.STRONG, InteractionType.EM])
    return stm


@pytest.fixture
def problem_sets(stm: StateTransitionManager) -> dict[float, list[ProblemSet]]:
    return stm.create_problem_sets()


@pytest.fixture
def qn_problem_and_result(
    stm: StateTransitionManager,
    problem_sets: dict[float, list[ProblemSet]],
) -> tuple[QNProblemSet, QNResult]:
    qn_solutions = stm.find_quantum_number_transitions(problem_sets)
    strong_qn_solutions = qn_solutions[3600.0]
    return strong_qn_solutions[1]
