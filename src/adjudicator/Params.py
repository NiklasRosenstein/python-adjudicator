from __future__ import annotations

from typing import Any, Collection, Generic, Iterable, KeysView, Mapping, Sequence, TypeAlias, TypeVar, cast, overload

from typeapi import type_repr

from adjudicator.HashSupport import Hasher
from adjudicator.Signature import Signature

T = TypeVar("T")
U = TypeVar("U")

_Sentinel = object()


class Params:
    """
    The Params class is a container for strongly typed parameters that can be passed to a rule. It serves as the
    container for the input parameters to a rule. It is a simple dictionary that maps a type to a value.

    The Params class is immutable. It can be merged with another Params instance using the `|` operator.

    Objects of types that have generic parameters must be specified explicitly using a dictionary. This is to avoid
    ambiguity when representing two instances of the same generic type with different parameters. For example, the
    following is not allowed:

    >>> from typing import Generic, TypeVar
    >>> T = TypeVar('T')
    >>> from dataclasses import dataclass
    >>> @dataclass(frozen=True)
    ... class MyGeneric(Generic[T]):
    ...   value: T
    >>> Params(MyGeneric[int](1), MyGeneric[str]("a"))
    Traceback (most recent call last):
    ValueError: A parameter of type `adjudicator.Params.MyGeneric` was specified in argument #0 of the \
Params() constructor, but was encountered again in argument #1.

    This is because the Params class would not be able to distinguish between the two instances of MyGeneric without
    additional runtime type information. Even a single instance of MyGeneric would not be allowed:

    >>> Params(MyGeneric[int](1))
    Traceback (most recent call last):
    AssertionError: Instance of parameterized generic type MyGeneric must be explicitly associated with type \
information.

    Instead, the following is allowed:

    >>> Params({
    ...     MyGeneric[int]: MyGeneric(1),
    ...     MyGeneric[str]: MyGeneric("a"),
    ... })
    Params(MyGeneric(value=1), MyGeneric(value='a'))

    The Params can be initialized with a tuple or list of objects, a dictionary of objects, objects directly, or
    multiple of either:

    >>> Params(42, {MyGeneric[int]: MyGeneric(1)})
    Params(42, MyGeneric(value=1))
    """

    InitType: TypeAlias = Sequence[object] | Mapping[type[Any], object] | "Params" | object

    _params: dict[type[Any], object]
    _hasher: Hasher

    def __init__(self, *args: InitType, hasher: Hasher | None = None):
        self._params = {}

        # Keep track of where each type was specified in the constructor arguments.
        arg_index_map: dict[type[Any], tuple[int, int]] = {}

        def format_arg_index(arg_index: tuple[int, int]) -> str:
            return (
                f"argument #{arg_index[0]}" if arg_index[1] == 0 else f"argument #{arg_index[0]}, item #{arg_index[1]}"
            )

        # Parse the arguments into the _params dictionary.
        for arg_idx, arg in enumerate(args):
            items: Iterable[tuple[type[Any], object]]
            if isinstance(arg, Params):
                items = arg._params.items()
                if hasher is None:
                    hasher = arg._hasher
            elif isinstance(arg, Mapping):
                items = arg.items()
            elif type(arg) in (list, tuple):
                assert isinstance(arg, (list, tuple))
                items = ((type(x), x) for x in arg)
            else:
                items = [(type(arg), arg)]

            for item_idx, (key, value) in enumerate(items):
                if key in self._params:
                    raise ValueError(
                        f"A parameter of type `{type_repr(key)}` was specified in "
                        f"{format_arg_index(arg_index_map[key])} of the Params() constructor, but was encountered "
                        f"again in {format_arg_index((arg_idx, item_idx))}."
                    )
                self._params[key] = value
                arg_index_map[key] = (arg_idx, item_idx)

        # Ensure that all generic types are explicitly associated with type information.
        for type_, obj in self._params.items():
            assert not (
                isinstance(type_, type) and issubclass(type_, Generic) and type_.__parameters__  # type: ignore
            ), "Instance of parameterized generic type {} must be explicitly associated with type information.".format(
                type_.__name__
            )
            if hasattr(type_, "__origin__"):
                type_ = type_.__origin__
            assert isinstance(obj, type_), "Object {} is not an instance of type {}".format(obj, type_)

        self._hasher = hasher or hash
        self._hash: int | None = None

    def __contains__(self, param_type: type[Any]) -> bool:
        return param_type in self._params

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = self._hasher(tuple(sorted(map(self._hasher, self._params.values()))))
        return self._hash

    #: If we have a consistent hasher, then the __hash__ method yields a consistent hash already.
    __persistent_hash__ = __hash__

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(map(repr, self._params.values()))})"

    def __or__(self, params: Params) -> Params:
        """
        Merge two parameter sets, taking precedence of the parameters in the right hand side.
        """

        return Params({**self._params, **params._params}, hasher=self._hasher)

    def __sub__(self, types: Collection[type[Any]]) -> Params:
        """
        Remove the parameters in the right hand side from the left hand side.
        """

        return Params({k: v for k, v in self._params.items() if k not in types}, hasher=self._hasher)

    def __len__(self) -> int:
        return len(self._params)

    def __bool__(self) -> bool:
        return bool(self._params)

    @overload
    def get(self, param_type: type[T]) -> T:
        ...

    @overload
    def get(self, param_type: type[T], default: U) -> T | U:
        ...

    def get(self, param_type: type[T], default: U | object = _Sentinel) -> T | U:
        try:
            return cast(T, self._params[param_type])
        except KeyError:
            if default is _Sentinel:
                raise KeyError(f"Parameter of type {param_type} not found")
            return cast(U, default)

    def items(self) -> Iterable[tuple[type[Any], object]]:
        return self._params.items()

    def types(self) -> KeysView[type[Any]]:
        return self._params.keys()

    def filter(self, types: Collection[type[Any]], total: bool = False) -> Params:
        """
        Return a new Params instance containing only the parameters of the specified types.
        """

        if total:
            return Params({t: self.get(t) for t in types}, hasher=self._hasher)
        else:
            return Params({t: self.get(t) for t in types if t in self}, hasher=self._hasher)

    def signature(self, output_type: type[Any]) -> Signature:
        """
        Obtain a signature for this set of parameters, with the specified output type.
        """

        return Signature(frozenset(self._params.keys()), output_type)

    def with_hasher(self, hasher: Hasher) -> Params:
        """
        Replace the hasher.
        """

        return Params(self, hasher=hasher)

    @property
    def hasher(self) -> Hasher:
        return self._hasher
