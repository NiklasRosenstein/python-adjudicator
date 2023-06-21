"""
Provides a generic, type based rules engine.
"""

from adjudicator.Cache import Cache
from adjudicator.errors import MultipleMatchingRulesError, NoMatchingRulesError, RuleResolveError
from adjudicator.Executor import Executor
from adjudicator.Params import Params
from adjudicator.Rule import Rule, collect_rules, rule
from adjudicator.RuleEngine import RuleEngine, get
from adjudicator.RuleGraph import RuleGraph

__all__ = [
    "Cache",
    "collect_rules",
    "Executor",
    "get",
    "MultipleMatchingRulesError",
    "NoMatchingRulesError",
    "Params",
    "rule",
    "Rule",
    "RuleResolveError",
    "RuleEngine",
    "RuleGraph",
]

__version__ = "0.2.1"
