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
