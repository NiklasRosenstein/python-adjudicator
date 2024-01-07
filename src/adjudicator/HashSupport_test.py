import subprocess as sp
import sys
from dataclasses import dataclass
from pickle import dumps
from typing import Any, Literal

from adjudicator.HashSupport import HashSupport


def hash_here_and_there(obj: Any, method: Literal["builtin", "persistent"]) -> tuple[int, int]:
    match method:
        case "builtin":
            hasher = hash
            hasher_expr = "hasher = hash"
        case "persistent":
            hasher = HashSupport()
            hasher_expr = "from adjudicator.HashSupport import HashSupport; hasher = HashSupport()"

    here = hasher(obj)

    code = f"{hasher_expr}; import pickle; print(hasher(pickle.loads({dumps(obj)!r})))"
    there = int(sp.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout)

    return here, there


def assert_hash_is_persistent(obj: Any, skip_builtin: bool = False) -> None:
    assert hash_here_and_there(obj, "persistent") == hash_here_and_there(obj, "persistent")
    if not skip_builtin:
        assert hash_here_and_there(obj, "builtin") != hash_here_and_there(obj, "builtin")


@dataclass(frozen=True)
class MyDataclass:
    foo: str
    bar: str


def test__persistent_hashing() -> None:
    assert_hash_is_persistent("foobar!")
    assert_hash_is_persistent(("foo", "bar", "baz"))
    assert_hash_is_persistent(["hello world"], skip_builtin=True)
    assert_hash_is_persistent({"foo": "bar"}, skip_builtin=True)
    assert_hash_is_persistent(MyDataclass("foo", "bar"))
