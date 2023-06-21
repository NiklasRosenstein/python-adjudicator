from pytest import raises

from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError
from adjudicator.rule import ProductionRule, UnionRule
from adjudicator.RuleGraph import RuleGraph
from adjudicator.Signature import Signature


def test__RulesGraph__get_production_rules() -> None:
    """
    Creates a rules graph like this:

        str -> int
        bool -> int
        int -> float

    And tests the output of `rules_for` for each type.
    """

    graph = RuleGraph(
        [
            ProductionRule(
                func=lambda p: int(p.get(str)),
                input_types=frozenset({str}),
                output_type=int,
                id="r1",
            ),
            ProductionRule(
                func=lambda p: int(p.get(bool)),
                input_types=frozenset({bool}),
                output_type=int,
                id="r2",
            ),
            ProductionRule(
                func=lambda p: float(p.get(int)),
                input_types=frozenset({int}),
                output_type=float,
                id="r3",
            ),
        ]
    )

    assert graph.get_production_rules(int) == {graph["r1"], graph["r2"]}
    assert graph.get_production_rules(float) == {graph["r3"]}


def test__RulesGraph__get_rules_for_output_type__with_union_membership() -> None:
    class A:
        pass

    class SpecificA(A):
        pass

    graph = RuleGraph(options=RuleGraph.Options(resolve_union_member_production_rules=True))
    graph.add_rules(
        [
            ProductionRule(
                func=lambda p: SpecificA(),
                input_types=frozenset({str}),
                output_type=SpecificA,
                id="r1",
            ),
        ]
    )

    assert graph.get_production_rules(SpecificA) == {graph["r1"]}
    assert graph.get_production_rules(A) == set()

    graph.add_rules([UnionRule(A, SpecificA)])
    assert graph.get_production_rules(A) == {graph["r1"]}


def test__RulesGraph__get_rules_for_output_type__returns_rules_without_inputs() -> None:
    graph = RuleGraph()
    graph.add_rules(
        [
            ProductionRule(
                func=lambda p: 42,
                input_types=frozenset(),
                output_type=int,
                id="r1",
            ),
        ]
    )
    assert graph.get_production_rules(int) == {graph["r1"]}


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
            ProductionRule(
                func=lambda p: int(p.get(str)),
                input_types=frozenset({str}),
                output_type=int,
                id="r1",
            ),
            ProductionRule(
                func=lambda p: int(p.get(bool)),
                input_types=frozenset({bool}),
                output_type=int,
                id="r2",
            ),
            ProductionRule(
                func=lambda p: bool(p.get(str)),
                input_types=frozenset({str}),
                output_type=bool,
                id="r3",
            ),
        ]
    )

    # There's a path for (bool) -> int.
    assert graph.find_path(Signature(frozenset({bool}), int)) == [graph["r2"]]

    # There's no singular path for (str) -> int as it cannot decide to go ((str) -> bool) -> int or (str) -> int.
    with raises(MultipleMatchingRulesError) as excinfo1:
        graph.find_path(Signature(frozenset({str}), int))
    assert sorted(excinfo1.value.paths, key=len) == [[graph["r1"]], [graph["r3"], graph["r2"]]]

    # There's no path for (float) -> bool.
    with raises(NoMatchingRulesError):
        graph.find_path(Signature(frozenset({float}), bool))
