from typing import Any, Callable

Hasher = Callable[[Any], int]


class HashSupport:
    """
    A helper class that supports in hashing objects. Usually it just defaults to the native #hash() function, but
    some otherwise unhashable types can be made hashable by providing a custom hash function.
    """

    def __init__(self) -> None:
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

        hash_func = self._custom_hashers.get(type(obj))
        if hash_func is not None:
            return hash_func(obj)

        for hash_func in self._fallback_hashers:
            try:
                result = hash_func(obj)
            except NotImplementedError:
                pass
            if result is not NotImplemented:
                return result

        return hash(obj)
