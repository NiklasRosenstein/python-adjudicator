import hashlib
import sys
from collections.abc import Sequence
from functools import partial
from types import NoneType
from typing import Any, Callable, Mapping

Hasher = Callable[[Any], int]


class HashSupport:
    """
    A helper class that supports in hashing objects. Usually it just defaults to the native #hash() function, but
    some otherwise unhashable types can be made hashable by providing a custom hash function. By default, it uses
    the #persistent_hash() function, which returns the same hash for the same object across separate Python program
    executions, however with limited built-in support for types.

    :param permit_not_persistent_hashing: If `True`, the #persistent_hash() function will fall back to the native
        #hash() function if it cannot hash the given object, resulting in a non-persistent hash. If `False`, it will
        # raise a `NotImplementedError` instead.
    """

    def __init__(self, permit_not_persistent_hashing: bool = False) -> None:
        self.default: Hasher = partial(
            persistent_hash,
            recurse=self,
            fallback=hash if permit_not_persistent_hashing else None,
        )
        self._custom_hashers: dict[type, Hasher] = {}
        self._fallback_hashers: list[Hasher] = []

    def register(self, type_: type, hash_function: Hasher) -> None:
        """
        Register a custom hash function for the given type.
        """

        self._custom_hashers[type_] = hash_function

    def fallback(self, hash_funtion: Hasher) -> None:
        """
        Register a fallback hash function that will be used if no custom hash function is registered for a given type.
        The function should either return `NotImplemented` or raise a `NotImplementedError` if it cannot hash the given
        object.
        """

        self._fallback_hashers.append(hash_funtion)

    def __call__(self, obj: Any) -> int:
        """
        Hash the given object.
        """

        for base in type(obj).__mro__:
            hash_func = self._custom_hashers.get(base)
            if hash_func is not None:
                return hash_func(obj)

        for hash_func in self._fallback_hashers:
            try:
                result = hash_func(obj)
            except NotImplementedError:
                pass
            if result is not NotImplemented:
                return result

        return self.default(obj)


def persistent_hash(obj: Any, recurse: Hasher, algorithm: str = "blake2b", fallback: Hasher | None = None) -> int:
    """
    A hash function that returns the same hash for the same object across separate Python program executions.
    """

    hasher = hashlib.new(algorithm)

    def hash_obj(obj: Any) -> None:
        hasher.update(type(obj).__name__.encode("utf-8"))
        match obj:
            case type():
                hasher.update(obj.__name__.encode("utf-8"))
                hasher.update(b";")
                return
            case int():
                # TODO: Support big integers?
                hasher.update(obj.to_bytes(8, "little", signed=True))
                return
            case str():
                hasher.update(obj.encode("utf-8"))
                return
            case bytes():
                hasher.update(obj)
                return
            case bool():
                hasher.update(obj.to_bytes(1, "little"))
                return
            case NoneType():
                return
            case Sequence():
                hasher.update(b"[")
                for item in obj:
                    hasher.update(recurse(item).to_bytes(8, "little", signed=True))
                hasher.update(b"]")
                return
        if isinstance(obj, Mapping):
            hasher.update(b"m{")
            for key, value in obj.items():
                hasher.update(recurse(key).to_bytes(8, "little", signed=True))
                hasher.update(b",")
                hasher.update(recurse(value).to_bytes(8, "little", signed=True))
                hasher.update(b";")
            hasher.update(b"}")
            return
        if hasattr(obj, "__dataclass_fields__"):
            hasher.update(b"D{")
            for field in obj.__dataclass_fields__.values():
                hasher.update(recurse(field.name).to_bytes(8, "little", signed=True))
                hasher.update(b",")
                hasher.update(recurse(getattr(obj, field.name)).to_bytes(8, "little", signed=True))
                hasher.update(b";")
            hasher.update(b"}")
            return
        if hasattr(obj, "__persistent_hash__"):
            hasher.update(obj.__persistent_hash__().to_bytes(8, "little", signed=True))
            return
        if fallback:
            hasher.update(hash(obj).to_bytes(8, "little", signed=True))
        else:
            raise NotImplementedError(f"Cannot consistent-hash object of type {type(obj)}")

    hash_obj(obj)
    digest = hasher.digest()
    return int.from_bytes(digest, "little", signed=True) % sys.maxsize
