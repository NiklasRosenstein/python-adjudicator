# adjudicator

> __Adjudicator__ _(nount_): An adjudicator is a person or body that makes formal judgments on a disputed matter. They
> are the ones who settle disputes or decide who is right in a disagreement. This could be a judge in a courtroom, an
> arbitrator in a negotiation, or any person or system given the power to make decisions of this type.

Adjudicator is a framework for implementing type-based rule engines largely inspired by the Pants build system. The
rule graph consists of nodes which are concrete Python types and edges which are functions that take a set of input
types and produce an output type.

Rules are matched on a set of facts, which populate the possible input types of a rule. Deriving a type may require
chained execution of rules, which is supported. Global facts may be used to populate a potential input type for all
rule executions.

The Adjudicator rule engine is designed to be used in a request-response fashion. A request is a set of facts that
should be used to derive a type. A response is the derived type. The rule engine will execute the rules necessary to
derive the type and return the response. If a rule was already executed with the same inputs, it will not be executed
again. For optimal use of the caching mechanism, all types participating in the rule evaluation should be immutable
and implement a stable hash (e.g. using `@dataclass(frozen=True)` and `tuple` instead of `list`, etc.).

When a mutable type should intentionally participate in the rule evaluation, usually this works automatically because
the hash of a Python object that does not provide a custom `__hash__()` implementation or disables its hashing is based
on the object's identity. This means that the hash is stable for the memory allocation of the object, and will not
change if the object is mutated. For types that do not _support_ hashing, support can be enabled explicitly using the
`RuleEngine.hashsupport` object.

__Table of Contents__

<!-- toc -->
* [Quickstart](#quickstart)
* [Installation](#installation)
* [Future Extensions](#future-extensions)
<!-- end toc -->

## Quickstart

The following example shows how to use Adjudicator to implement a simple "Hello World" application. The rule engine
invokes the `say_hello()` production rule because a `HelloResponse` is requested and a `HelloRequest` is provided,
which matches the rule's signature.

<!-- include code:python examples/hello.py -->
```python
from dataclasses import dataclass
from adjudicator import Params, RuleEngine, rule

@dataclass(frozen=True)
class HelloRequest:
    name: str

@dataclass(frozen=True)
class HelloResponse:
    greeting: str

@rule()
def say_hello(request: HelloRequest) -> HelloResponse:
    return HelloResponse(greeting=f"Hello {request.name}!")

engine = RuleEngine()
engine.load_module(__name__)
response = engine.get(HelloResponse, Params(HelloRequest(name="World")))
print(response.greeting)
```
<!-- end include -->

A more complex example can be found in the [mksync](https://github.com/NiklasRosenstein/mksync) project.

## Installation

Adjudicator is available on PyPI. You need at least Python 3.10.

```bash
pip install python-adjudicator
```

## Future Extensions

* Currently the rule graph stores rules as connections between types and rules on edges. A more efficient
  representation would be the one illustrated above, where types are connected to rules which are connected to types.
* The ability to mark facts as required to be consumed. If such a fact is not consumed during the execution of a
  request, an error will be raised.
