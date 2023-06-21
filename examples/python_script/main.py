import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from adjudicator import RuleEngine, get, rule


@dataclass(frozen=True)
class PythonBinaryRequest:
    pass


@dataclass(frozen=True)
class PythonBinary:
    path: Path
    version: str


@dataclass(frozen=True)
class PythonScriptExecutionRequest:
    path: Path


@dataclass(frozen=True)
class PythonScriptExecutionResult:
    exit_code: int


@rule
def python_binary_from_request(request: PythonBinaryRequest) -> PythonBinary:
    return PythonBinary(path=Path(sys.executable), version=".".join(map(str, sys.version_info[:3])))


@rule
def python_script_execute(request: PythonScriptExecutionRequest, binary: PythonBinary) -> PythonScriptExecutionResult:
    command = [str(binary.path), str(request.path)]
    exit_code = subprocess.run(command).returncode
    return PythonScriptExecutionResult(exit_code=exit_code)


if __name__ == "__main__":
    script_path = Path(__file__).parent / "script.py"

    engine = RuleEngine()
    engine.add_rules(globals())

    with engine.as_current():
        print("Executing script")
        response = get(
            PythonScriptExecutionResult,
            PythonScriptExecutionRequest(path=script_path),
            PythonBinaryRequest(),
        )
        print("Executing script again ..?")
        response = get(
            PythonScriptExecutionResult,
            PythonScriptExecutionRequest(path=script_path),
            PythonBinaryRequest(),
        )
        print("Nope!")
    sys.exit(response.exit_code)
