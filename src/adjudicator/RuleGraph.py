from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping, TypedDict, TypeVar

from networkx import MultiDiGraph
from networkx.algorithms.dag import is_directed_acyclic_graph
from typing_extensions import TypeAlias

from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError, RuleResolveError
from adjudicator.rule import ProductionRule, RuleTypes, UnionRule
from adjudicator.Signature import Signature

T = TypeVar("T")


class NoInputs:
    """
    This type is used in the rules graph to indicate when a rule takes no inputs.
    """


class Edge(TypedDict):
    rule: RuleTypes


@dataclass(frozen=True)
class RuleGraphOptions:
    """
    Options for the rule graph.
    """

    #: If this flag is enabled, the RuleGraph will resolve union member types to their union type
    #: when resolving the production rules for a given output type.
    resolve_union_member_production_rules: bool = False


class RuleGraph:
    """
    This graph contains types as the nodes and rules are the edges, as well as information on union types.
    """

    Options: TypeAlias = RuleGraphOptions

    def __init__(self, rules: Iterable[RuleTypes] | RuleGraph = (), options: RuleGraphOptions | None = None) -> None:
        self._rules: dict[str, RuleTypes] = {}
        self._unions: Mapping[type[Any], set[type[Any]]] = defaultdict(set)

        if isinstance(rules, RuleGraph):
            if options is None:
                options = rules._options
            rules = list(rules._rules.values())
        else:
            rules = list(rules)

        self._graph = MultiDiGraph()
        self._options: RuleGraphOptions = options or RuleGraphOptions()
        self.add_rules(rules)

    def __iter__(self) -> Iterable[RuleTypes]:
        return iter(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def __getitem__(self, rule_id: str) -> RuleTypes:
        return self._rules[rule_id]

    def get_union_members(self, type_: type[T]) -> Collection[type[T]]:
        """
        Return all types that are members of the specified union type.
        """

        return self._unions[type_]

    def add_rules(self, rules: Iterable[RuleTypes]) -> None:
        """
        Add more rules to the graph.
        """

        for rule in rules:
            match rule:
                case ProductionRule():
                    if rule.id in self._rules:
                        raise ValueError("Duplicate rule ID: " + rule.id)
                    self._rules[rule.id] = rule
                    self._graph.add_nodes_from(rule.input_types)
                    self._graph.add_node(rule.output_type)
                    for input_type in rule.input_types or {NoInputs}:
                        self._graph.add_edge(input_type, rule.output_type, **Edge(rule=rule))
                case UnionRule():
                    self._unions[rule.union_type].add(rule.member_type)
                    if self._options.resolve_union_member_production_rules:
                        self._graph.add_node(rule.union_type)
                        self._graph.add_node(rule.member_type)
                        self._graph.add_edge(rule.member_type, rule.union_type, **Edge(rule=rule))
                case _:
                    assert False, f"Unknown rule type: {rule}"

        if not is_directed_acyclic_graph(self._graph):  # type: ignore[no-untyped-call]
            raise ValueError("Rules graph is not acyclic")

    def get_production_rules(self, output_type: type[Any]) -> set[ProductionRule]:
        """
        Return all rules that can generate the specified output type.
        """

        rules: set[ProductionRule] = set()
        if output_type not in self._graph.nodes:
            return rules
        for edge in self._graph.in_edges(output_type):
            data: Edge
            for data in self._graph.get_edge_data(*edge).values():
                match data["rule"]:
                    case ProductionRule():
                        rules.add(data["rule"])
                    case UnionRule():
                        rules.update(self.get_production_rules(edge[0]))
                    case _:
                        assert False, type(data["rule"])
        return rules

    def find_path(self, sig: Signature) -> list[ProductionRule]:
        """
        Returns the path from the *input_types* to the *output_type*.
        """

        rules = self.get_production_rules(sig.output_type)

        results: list[list[ProductionRule]] = []
        for rule in rules:
            # Find the paths to satisfy missing inputs of the rule.
            try:
                rules_to_satify_missing_inputs: list[ProductionRule] = []
                for missing_input_type in rule.input_types - sig.inputs:
                    for inner_rule in self.find_path(Signature(sig.inputs, missing_input_type)):
                        if inner_rule not in rules_to_satify_missing_inputs:
                            rules_to_satify_missing_inputs.append(inner_rule)
            except RuleResolveError:
                continue

            results.append([*rules_to_satify_missing_inputs, rule])

        if len(results) > 1:
            raise MultipleMatchingRulesError(sig, results, self)
        if len(results) == 0:
            raise NoMatchingRulesError(sig, self)
        return results[0]
