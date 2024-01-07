from __future__ import annotations

import importlib
import inspect
from collections import ChainMap
from dataclasses import dataclass, field
from functools import wraps
from itertools import chain
from typing import Any, Callable, Mapping, ParamSpec, TypeVar, overload
from uuid import uuid4

from typeapi import get_annotations, type_repr

from adjudicator.Params import Params
from adjudicator.Signature import Signature

T = TypeVar("T")
P = ParamSpec("P")


@dataclass(frozen=True)
class ProductionRule:
    """
    A production rule represents a unit of work that can produce an object of a given output type from a given
    set of input types.
    """

    func: Callable[[Params], Any]
    input_types: frozenset[type[Any]]
    output_type: type[Any]
    description: str | None = None
    persistent_caching: bool = True  # If enabled, the result of the rule should be cached persistently.
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        assert isinstance(self.input_types, frozenset)
        assert isinstance(self.output_type, type)

    def __repr__(self) -> str:
        return f"<Rule {self.id!r} ({', '.join(map(type_repr, self.input_types))}) -> {type_repr(self.output_type)}>"

    @property
    def signature(self) -> Signature:
        return Signature(self.input_types, self.output_type)

    @staticmethod
    def of(func: Callable[..., Any], metadata: ProductionRuleMetadata | None = None) -> ProductionRule:
        """
        Create a rule from a function. The function must have type annotations for all parameters and the return value.
        """

        annotations = get_annotations(func)
        output_type = annotations.pop("return")
        input_types = {v: k for k, v in annotations.items()}
        metadata = metadata or ProductionRuleMetadata()

        if len(input_types) != len(annotations):
            raise RuntimeError("Rule function must not have overlapping type annotations")
        if output_type in input_types:
            raise RuntimeError("Rule function must not have overlapping type annotations")
        if len(input_types) != len(inspect.signature(func).parameters):
            raise RuntimeError("Rule function must have type annotations for all parameters and return value")

        @wraps(func)
        def _wrapper(params: Params) -> Any:
            return func(**{k: params.get(v) for v, k in input_types.items()})

        return ProductionRule(
            _wrapper,
            frozenset(input_types),
            output_type,
            metadata.description,
            metadata.persistent_caching,
            func.__module__ + "." + func.__qualname__,
        )


@dataclass(frozen=True)
class UnionRule:
    """
    This rule indicates to the rule engine that whenever a rule for the #union_type is searched, a rule that produces
    the #member_type is just as applicable. Note #member_type should be a subclass of #union_type.
    """

    union_type: type[Any]
    member_type: type[Any]
    id: str = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.id is None:
            object.__setattr__(self, "id", f"{type_repr(self.union_type)} ∈ {type_repr(self.member_type)}")  # type: ignore[unreachable]  # noqa: E501


RuleTypes = ProductionRule | UnionRule


##
# @rule() decorator
##


@dataclass(frozen=True)
class ProductionRuleMetadata:
    description: str | None = None
    persistent_caching: bool = True


def rule(
    *, description: str | None = None, persistent_caching: bool = True
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for functions to be used as production rules. Marks the function with a `__adjudicator_rule__` attribute.
    The #collect_rules() function can be used to collect all functions marked with this attribute from a dictionary or
    module.
    """

    metadata = ProductionRuleMetadata(description, persistent_caching)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        setattr(func, "__adjudicator_rule__", metadata)
        return func

    return decorator


##
# @union() and @union_rule()
##


@dataclass(frozen=True)
class UnionRuleMetadata:
    bases: tuple[type[Any], ...]


def union() -> Callable[[type[T]], type[T]]:
    """
    Decorator for types to mark them as union types.
    """

    def decorator(type_: type[T]) -> type[T]:
        setattr(type_, "__adjudicator_union__", True)
        return type_

    return decorator


def is_union(type_: type[Any]) -> bool:
    """
    Check if a type is a union type.
    """

    return getattr(type_, "__adjudicator_union__", False)


def union_rule(union_type: type[Any] | None = None) -> Callable[[type[T]], type[T]]:
    """
    Decorator for subclasses of a `@union()` decorated type. Marks the class as a union member of that type.

    If the #union_type is not specified, it is inferred from the class' base classes.
    """

    def decorator(type_: type[T]) -> type[T]:
        if union_type is None:
            bases = tuple(b for b in type_.__bases__ if is_union(b))
            if not bases:
                raise TypeError(
                    f"Cannot infer union type for {type_!r} because it has no base classes that are marked "
                    "with the @union decorator."
                )
        else:
            bases = (union_type,)

        metadata = UnionRuleMetadata(bases)
        setattr(type_, "__adjudicator_union_rule__", metadata)
        return type_

    return decorator


##
# collect_rules()
##


@overload
def collect_rules(obj: str | Mapping[str, Any] | object, /) -> list[RuleTypes]:
    ...


@overload
def collect_rules(*, stackdepth: int = 0) -> list[RuleTypes]:
    ...


def collect_rules(
    obj: str | Mapping[str, Any] | object | None = None,
    *,
    stackdepth: int = 0,
) -> list[RuleTypes]:
    """
    Collect all rules from the specified globals and locals. If they are not specified, the globals and locals of the
    calling frame are used.
    """

    def get_scope(stack: list[inspect.FrameInfo]) -> Mapping[str, Any]:
        container = id(stack[0].frame.f_globals)
        locals = []
        for frame in stack:
            if id(frame.frame.f_globals) == container:
                locals.append(frame.frame.f_locals)
        return ChainMap(*locals, stack[0].frame.f_globals)

    if obj is None:
        obj = get_scope(inspect.stack()[stackdepth + 1 :])
    elif isinstance(obj, str):
        module = importlib.import_module(obj)
        obj = module.__dict__
    elif not isinstance(obj, Mapping):
        obj = {k: getattr(obj, k, None) for k in dir(obj) if not k.startswith("__")}

    result: list[RuleTypes] = []
    for v in chain(obj.values()):
        if callable(v) and (metadata := getattr(v, "__adjudicator_rule__", None)):
            result.append(ProductionRule.of(v, metadata))
        elif isinstance(v, type) and (metadata := getattr(v, "__adjudicator_union_rule__", None)):
            for base in metadata.bases:
                result.append(UnionRule(base, v))
    return result
