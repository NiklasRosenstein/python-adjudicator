from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adjudicator.Params import Params
    from adjudicator.rule import ProductionRule

_sentinel = object()


class Cache(ABC):
    """
    Base class for all cache implementations.
    """

    @abstractmethod
    def has(self, rule: ProductionRule, params: Params) -> bool:
        """
        Return True if the specified rule and params have been evaluated.
        """

    @abstractmethod
    def get(self, rule: ProductionRule, params: Params) -> Any:
        """
        Return the result of evaluating the specified rule and params.

        Raise a #KeyError if the specified rule and params have not been evaluated.
        """

    @abstractmethod
    def set(self, rule: ProductionRule, params: Params, value: Any) -> None:
        """
        Set the result of evaluating the specified rule and params.
        """

    @staticmethod
    def none() -> "Cache":
        """
        Return a new cache that does not cache anything.
        """

        return NoneCache()

    @staticmethod
    def memory() -> "Cache":
        """
        Return a new memory cache.
        """

        return MemoryCache()


class NoneCache(Cache):
    """
    Cache implementation that does not cache anything.
    """

    def has(self, rule: ProductionRule, params: Params) -> bool:
        return False

    def get(self, rule: ProductionRule, params: Params) -> Any:
        raise KeyError()

    def set(self, rule: ProductionRule, params: Params, value: Any) -> None:
        pass


class MemoryCache(Cache):
    """
    In-memory cache implementation.
    """

    def __init__(self) -> None:
        self._cache: dict[int, Any] = {}
        self._persistent_cache: dict[int, Any] = {}

    def __getstate__(self) -> tuple[dict[int, Any],]:
        return (self._persistent_cache,)

    def __setstate__(self, state: tuple[dict[int, Any],]) -> None:
        self._cache = {}
        (self._persistent_cache,) = state

    def has(self, rule: ProductionRule, params: Params) -> bool:
        hash_code = params.hasher((rule.id, params))
        return hash_code in self._cache or hash_code in self._persistent_cache

    def get(self, rule: ProductionRule, params: Params) -> Any:
        hash_code = params.hasher((rule.id, params))
        result = self._cache.get(hash_code, _sentinel)
        if result is _sentinel:
            result = self._persistent_cache[hash_code]
        return result

    def set(self, rule: ProductionRule, params: Params, value: Any) -> None:
        if rule.persistent_caching:
            dest = self._persistent_cache
        else:
            dest = self._cache
        dest[params.hasher((rule.id, params))] = value
