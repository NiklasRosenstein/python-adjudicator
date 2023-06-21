import sys
from dataclasses import dataclass

from pytest import mark

from adjudicator.Cache import Cache
from adjudicator.Executor import Executor
from adjudicator.Params import Params
from adjudicator.rule import ProductionRule, collect_rules, rule
from adjudicator.RuleEngine import RuleEngine, get

sys.setrecursionlimit(130)


@mark.parametrize(
    argnames="cache_impl,is_cached",
    argvalues=[
        (Cache.memory(), True),
        (Cache.none(), False),
    ],
    ids=["memory", "none"],
)
def test__RulesEngine__can_cache_properly(cache_impl: Cache, is_cached: bool) -> None:
    """
    Tests if rule result caching works as expected.
    """

    @dataclass(frozen=True)
    class Fibonacci:
        n: int

    num_invokations = 0

    @rule()
    def fibonacci(n: int) -> Fibonacci:
        nonlocal num_invokations
        num_invokations += 1
        if n < 2:
            return Fibonacci(n)
        x = get(Fibonacci, n - 1)
        y = get(Fibonacci, n - 2)
        return Fibonacci(x.n + y.n)

    engine = RuleEngine(list(collect_rules()), [], executor=Executor.simple(cache=cache_impl))

    assert engine.get(Fibonacci, Params([0])).n == 0
    assert engine.get(Fibonacci, Params([3])).n == 2
    assert engine.get(Fibonacci, Params([4])).n == 3
    assert engine.get(Fibonacci, Params([5])).n == 5
    assert engine.get(Fibonacci, Params([6])).n == 8
    assert num_invokations == 7 if is_cached else 55
    assert engine.get(Fibonacci, Params([7])).n == 13
    assert num_invokations == 8 if is_cached else 96


def test__RulesEngine__picks_correct_rule_for_same_output() -> None:
    engine = RuleEngine(
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
        ],
        facts=[],
    )

    assert engine.get(int, Params(["42"])) == 42
    assert engine.get(int, Params([True])) == 1
    assert engine.get(int, Params([False])) == 0


def test__RulesEngine__injects_facts() -> None:
    @dataclass(frozen=True)
    class CustomType:
        v: int

    engine = RuleEngine(
        rules=[
            ProductionRule(
                func=lambda p: p.get(CustomType).v,
                input_types=frozenset({CustomType}),
                output_type=int,
                id="r1",
            )
        ],
        facts=[CustomType(42)],
    )

    assert engine.get(int, Params()) == 42
    assert engine.get(int, Params([CustomType(33)])) == 33
