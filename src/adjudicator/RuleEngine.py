from __future__ import annotations

from contextlib import contextmanager
from typing import Any, ClassVar, Iterable, Iterator, Mapping, TypeVar

from adjudicator import collect_rules
from adjudicator.Cache import Cache
from adjudicator.Executor import Executor
from adjudicator.HashSupport import HashSupport
from adjudicator.Params import Params
from adjudicator.Rule import Rule
from adjudicator.RuleGraph import RuleGraph
from adjudicator.Signature import Signature

T = TypeVar("T")


class RuleEngine:
    """
    A simple rules engine.

    It is composed of rules, built-in facts (i.e. parameters that are available to all rules), an executor for
    executing rules, a cache for caching rule results and a registry of union types.
    """

    def __init__(
        self,
        rules: Iterable[Rule] | RuleGraph = (),
        facts: Params.InitType | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.graph = RuleGraph(rules)
        self.hashsupport = HashSupport()
        self.facts = Params(facts or (), hasher=self.hashsupport)
        self.executor = executor or Executor.simple(Cache.memory())

    _current_engine_stack: ClassVar[list[RuleEngine]] = []

    @contextmanager
    def as_current(self) -> Iterator[None]:
        """
        Set the engine as the current engine for the duration of the context. Calls to #current() will return it
        as long as the context manager is active.
        """

        try:
            RuleEngine._current_engine_stack.append(self)
            yield
        finally:
            assert RuleEngine._current_engine_stack.pop() is self

    @staticmethod
    def current() -> "RuleEngine":
        if RuleEngine._current_engine_stack:
            return RuleEngine._current_engine_stack[-1]
        raise RuntimeError("No current RuleEngine")

    def get(self, output_type: type[T], params: Params) -> T:
        """
        Evaluate the rules to derive the specified *output_type* from the given parameters.
        """

        if not params and output_type in self.facts:
            return self.facts.get(output_type)

        sig = Signature(set(params.types()) | set(self.facts.types()), output_type)
        rules = self.graph.find_path(sig)
        assert len(rules) > 0, "Empty path?"

        output: Any = None
        for rule in rules:
            inputs = self.facts.filter(rule.input_types) | params.filter(rule.input_types)
            output = self.executor.execute(rule, inputs, self)
            params = params | Params({rule.output_type: output}, hasher=self.hashsupport)

        assert isinstance(output, output_type), f"Expected {output_type}, got {type(output)}"
        return output

    def add_rules(self, rules: Iterable[Rule] | Mapping[str, Any]) -> None:
        if isinstance(rules, Mapping):
            rules = collect_rules(globals=rules)
        self.graph.add_rules(rules)

    def assert_facts(self, facts: Params.InitType) -> None:
        """
        Assert facts to the rules engine. Note that this will fail if a fact of the given type already exists in
        the rules engine.
        """

        facts = Params(facts)
        overlap = self.facts.types() & facts.types()
        if overlap:
            raise ValueError(f"Fact(s) of type {overlap} already exist(s)")
        self.facts = self.facts | facts

    def retract_facts(self, facts: Params.InitType) -> None:
        """
        Retract facts from the rules engine. Note that this will fail if a fact of the given type does not exist in
        the rules engine, or if the value specfified for a type does not match the value in the rules engine.
        """

        facts = Params(facts)
        missing = facts.types() - self.facts.types()
        if missing:
            raise ValueError(f"Fact(s) of type {missing} do(es) not exist(s)")

        for type_, fact in facts.items():
            existing_fact = self.facts.get(type_)
            if fact != existing_fact:
                raise ValueError(
                    f"Cannot retract fact of type {type_} because the fact provided does not match the same type of "
                    "fact in the rules engine."
                )

        self.facts = self.facts - facts.types()


def get(output_type: type[T], *inputs: object) -> T:
    """
    Delegate to the engine to retrieve the specified output type given the input parameters. If the first argument
    is a dictionary, it will be used as the input parameters and no arguments can follow.
    """

    engine = RuleEngine.current()

    if inputs and isinstance(inputs[0], dict):
        assert len(inputs) == 1, "No arguments allowed after dictionary"
        params = Params(inputs[0], hasher=engine.hashsupport)
    else:
        params = Params(inputs, hasher=engine.hashsupport)

    return engine.get(output_type, params)