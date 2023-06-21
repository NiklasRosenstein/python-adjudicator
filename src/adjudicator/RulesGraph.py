from __future__ import annotations

from collections import defaultdict
from typing import Any, Collection, Iterable, Literal, Mapping, TypedDict

from networkx import MultiDiGraph
from networkx.algorithms.dag import is_directed_acyclic_graph
from typing_extensions import NotRequired

from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError, RuleResolveError
from adjudicator.Rule import Rule
from adjudicator.Signature import Signature


class NoInputs:
    """
    This type is used in the rules graph to indicate when a rule takes no inputs.
    """


class Edge(TypedDict):
    type: Literal["rule", "union"]
    rule: NotRequired[Rule]


class RulesGraph:
    """
    This graph contains types as the nodes and rules are the edges, as well as information on union types.
    """

    def __init__(self, rules: Iterable[Rule] | RulesGraph = ()) -> None:
        self._rules: dict[str, Rule] = {}
        self._unions: Mapping[type[Any], set[type[Any]]] = defaultdict(set)

        if isinstance(rules, RulesGraph):
            rules = list(rules._rules.values())
        else:
            rules = list(rules)

        self._graph = MultiDiGraph()
        self.add_rules(rules)

    def __iter__(self) -> Iterable[Rule]:
        return iter(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def __getitem__(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def get_union_members(self, type_: type[Any]) -> Collection[type[Any]]:
        """
        Return all types that are members of the specified union type.
        """

        return self._unions[type_]

    def register_union_member(self, union_type: type[Any], member_type: type[Any]) -> None:
        """
        Register a new union member to the graph. This produces an edge from the *member_type* to the *union_type*,
        allowing the graph to treat the *member_type* as if it is the *union_type* when resolving the *union_type*.
        """

        self._unions[union_type].add(member_type)
        self._graph.add_node(union_type)
        self._graph.add_node(member_type)
        self._graph.add_edge(member_type, union_type, **Edge(type="union"))

    def add_rules(self, rules: Iterable[Rule]) -> None:
        """
        Add more rules to the graph.
        """

        for rule in rules:
            if rule.id in self._rules:
                raise ValueError("Duplicate rule ID: " + rule.id)
            self._rules[rule.id] = rule
            self._graph.add_nodes_from(rule.input_types)
            self._graph.add_node(rule.output_type)
            for input_type in rule.input_types or {NoInputs}:
                self._graph.add_edge(input_type, rule.output_type, **Edge(type="rule", rule=rule))
        if not is_directed_acyclic_graph(self._graph):  # type: ignore[no-untyped-call]
            raise ValueError("Rules graph is not acyclic")

    def get_rules_for_output_type(self, output_type: type[Any]) -> set[Rule]:
        """
        Return all rules that can generate the specified output type.
        """

        rules: set[Rule] = set()
        if output_type not in self._graph.nodes:
            return rules
        for edge in self._graph.in_edges(output_type):
            data: Edge
            for data in self._graph.get_edge_data(*edge).values():
                match data["type"]:
                    case "rule":
                        rules.add(data["rule"])
                    case "union":
                        rules.update(self.get_rules_for_output_type(edge[0]))
                    case _:
                        assert False, data["type"]
        return rules

    def find_path(self, sig: Signature) -> list[Rule]:
        """
        Returns the path from the *input_types* to the *output_type*.
        """

        rules = self.get_rules_for_output_type(sig.output_type)

        results: list[list[Rule]] = []
        for rule in rules:
            # Find the paths to satisfy missing inputs of the rule.
            try:
                rules_to_satify_missing_inputs: list[Rule] = []
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
