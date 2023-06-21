from dataclasses import dataclass
from typing import Generic, TypeVar

from pytest import raises

from adjudicator import Params

T = TypeVar("T")


@dataclass(frozen=True)
class MyGeneric(Generic[T]):
    value: T


def test__Params__cannot_delinate_between_instances_of_different_generic_types() -> None:
    with raises(ValueError) as excinfo:
        Params([MyGeneric[int](1), MyGeneric[str]("a")])
    assert (
        str(excinfo.value) == "A parameter of type `adjudicator.Params_test.MyGeneric` was specified in argument "
        "#0 of the Params() constructor, but was encountered again in argument #0, item #1."
    )


def test__Params__can_delinate_between_instances_of_different_generic_types_when_explicitly_specified() -> None:
    params = Params(
        {
            MyGeneric[int]: MyGeneric(1),
            MyGeneric[str]: MyGeneric("a"),
        }
    )
    assert params.get(MyGeneric[int]) == MyGeneric(1)
    assert params.get(MyGeneric[str]) == MyGeneric("a")

    with raises(KeyError):
        assert params.get(MyGeneric)
