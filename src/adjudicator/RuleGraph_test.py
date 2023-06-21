from pytest import raises

from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError
from adjudicator.Rule import Rule
from adjudicator.RuleGraph import RuleGraph
from adjudicator.Signature import Signature


def test__RulesGraph__get_rules_for_output_type() -> None:
    """
    Creates a rules graph like this:

        str -> int
        bool -> int
        int -> float

    And tests the output of `rules_for` for each type.
    """

    graph = RuleGraph(
        [
            Rule(
                func=lambda p: int(p.get(str)),
                input_types={str},
                output_type=int,
                id="r1",
            ),
            Rule(
                func=lambda p: int(p.get(bool)),
                input_types={bool},
                output_type=int,
                id="r2",
            ),
            Rule(
                func=lambda p: float(p.get(int)),
                input_types={int},
                output_type=float,
                id="r3",
            ),
        ]
    )

    assert graph.get_rules_for_output_type(int) == {graph["r1"], graph["r2"]}
    assert graph.get_rules_for_output_type(float) == {graph["r3"]}


def test__RulesGraph__get_rules_for_output_type__with_union_membership() -> None:
    class A:
        pass

    class SpecificA(A):
        pass

    graph = RuleGraph()
    graph.add_rules(
        [
            Rule(
                func=lambda p: SpecificA(),
                input_types={str},
                output_type=SpecificA,
                id="r1",
            ),
        ]
    )

    assert graph.get_rules_for_output_type(SpecificA) == {graph["r1"]}
    assert graph.get_rules_for_output_type(A) == set()

    graph.register_union_member(A, SpecificA)
    assert graph.get_rules_for_output_type(A) == {graph["r1"]}


def test__RulesGraph__get_rules_for_output_type__returns_rules_without_inputs() -> None:
    graph = RuleGraph()
    graph.add_rules(
        [
            Rule(
                func=lambda p: 42,
                input_types=set(),
                output_type=int,
                id="r1",
            ),
        ]
    )
    assert graph.get_rules_for_output_type(int) == {graph["r1"]}


def test__RulesGraph__find_path__cannot_resolve_diamond_dependency() -> None:
    """
    Builds a rules graph like this:

        str -> int
        str -> bool -> int

    When the requested signature is `(str) -> int`, the engine should raise an exception as it cannot decide
    whether to use the short or the long path.
    """

    graph = RuleGraph(
        rules=[
            Rule(
                func=lambda p: int(p.get(str)),
                input_types={str},
                output_type=int,
                id="r1",
            ),
            Rule(
                func=lambda p: int(p.get(bool)),
                input_types={bool},
                output_type=int,
                id="r2",
            ),
            Rule(
                func=lambda p: bool(p.get(str)),
                input_types={str},
                output_type=bool,
                id="r3",
            ),
        ]
    )

    # There's a path for (bool) -> int.
    assert graph.find_path(Signature({bool}, int)) == [graph["r2"]]

    # There's no singular path for (str) -> int as it cannot decide to go ((str) -> bool) -> int or (str) -> int.
    with raises(MultipleMatchingRulesError) as excinfo1:
        graph.find_path(Signature({str}, int))
    assert sorted(excinfo1.value.paths, key=len) == [[graph["r1"]], [graph["r3"], graph["r2"]]]

    # There's no path for (float) -> bool.
    with raises(NoMatchingRulesError):
        graph.find_path(Signature({float}, bool))
