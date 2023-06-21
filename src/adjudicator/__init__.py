"""
Provides a generic, type based rules engine.
"""

from adjudicator.Cache import Cache
from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError, RuleResolveError
from adjudicator.Executor import Executor
from adjudicator.Params import Params
from adjudicator.rule import ProductionRule, UnionRule, collect_rules, is_union, rule, union, union_rule
from adjudicator.RuleEngine import RuleEngine, get
from adjudicator.RuleGraph import RuleGraph

__all__ = [
    "Cache",
    "collect_rules",
    "Executor",
    "get",
    "is_union",
    "MultipleMatchingRulesError",
    "NoMatchingRulesError",
    "Params",
    "ProductionRule",
    "rule",
    "RuleEngine",
    "RuleGraph",
    "RuleResolveError",
    "union_rule",
    "union",
    "UnionRule",
]

__version__ = "0.3.0"
