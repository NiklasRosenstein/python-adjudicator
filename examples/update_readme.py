from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, TypeVar

from adjudicator import Params, RuleEngine, RuleGraph, get, rule, union, union_rule

T = TypeVar("T")


@dataclass
class Context:
    targets: list[Any] = field(default_factory=list)

    def __lshift__(self, target: Any) -> None:
        self.targets.append(target)

    def select(self, type_: type[T]) -> Iterator[T]:
        for target in self.targets:
            if isinstance(target, type_):
                yield target


@dataclass(frozen=True)
class ReadFileRequest:
    path: Path


@dataclass(frozen=True)
class ReadFile:
    content: str


@rule()
def _read_file(request: ReadFileRequest) -> ReadFile:
    return ReadFile(content=request.path.read_text())


@dataclass(frozen=True)
class PreprocessFileTarget:
    """
    Represents that a given file should be preprocessed.
    """

    path: Path


@dataclass(frozen=True)
class PreprocessFileResult:
    content: str
    num_directives: int


@rule()
def _preprocess_file(file: PreprocessFileTarget) -> PreprocessFileResult:
    content = get(ReadFile, ReadFileRequest(file.path)).content
    offset = 0
    directives = get(PreprocessorDirectives, file)
    for directive in sorted(directives, key=lambda d: d.begin):
        replacement = get(RenderedDirective, directive)
        content = content[: directive.begin + offset] + replacement.text + content[directive.end + offset :]
        offset += len(replacement.text) - (directive.end - directive.begin)
    return PreprocessFileResult(content=content, num_directives=len(directives))


@dataclass
class RenderedDirective:
    text: str


@union()
@dataclass(frozen=True)
class PreprocessorDirective:
    begin: int
    end: int


class GenericPreprocessorDirectives(tuple[T, ...]):
    pass


@union()
class PreprocessorDirectives(GenericPreprocessorDirectives[PreprocessorDirective]):
    """
    Represents a list of preprocessor directives in a Markdown file.
    """


@rule()
def _get_preprocessor_directives(request: PreprocessFileTarget) -> PreprocessorDirectives:
    """
    Fetches all preprocessor directives that can be found in the *request*.
    """

    members = get(RuleGraph).get_union_members(PreprocessorDirectives)
    results: list[PreprocessorDirective] = []
    for member in members:
        results += get(member, request)
    return PreprocessorDirectives(results)


@dataclass(frozen=True)
class ParsedDirective:
    begin: str
    end: str
    opts: str


def parse_directives(text: str, keyword: str) -> Iterator[ParsedDirective]:
    begin_regex = re.compile(r"<!--\s*" + re.escape(keyword) + r"(.*)?\s*-->")
    end_regex = re.compile(r"<!--\s*end\s*" + re.escape(keyword) + r"\s*-->")
    offset = 0

    begin_match = begin_regex.search(text)
    while offset < len(text) and begin_match is not None:
        opts = begin_match.group(1).strip()
        begin = offset + begin_match.start()
        end_match = end_regex.search(text, begin_match.end())
        next_begin_match = begin_regex.search(text, begin_match.end())

        if end_match is None or (next_begin_match and next_begin_match.start() < end_match.start()):
            end = begin_match.end()
            offset = begin_match.end()
        else:
            end = end_match.end()
            offset = end_match.end()
        yield ParsedDirective(begin, end, opts)

        begin_match = next_begin_match


@dataclass(frozen=True)
@union_rule()
class IncludeFileDirective(PreprocessorDirective):
    """
    Represents a request to include the contents of a file in a Markdown file, declared with an
    `<!-- include:<filename> -->` directive. The directive may be terminated with a `<!-- end include -->` directive.
    If no such termination is found, the opening tag of the directive suffices to include the file.

    An optional `code:<lang>` attribute may be specified to indicate that the file should be included as a code block
    with the specified language.
    """

    filename: str
    code: str | None

    @classmethod
    def parse(cls, text: str) -> Iterator[IncludeFileDirective]:
        regex = re.compile(r"(.*?)(?:\s+code:([^ ]+))?$")
        for directive in parse_directives(text, "include"):
            m = regex.match(directive.opts)
            filename, code = m.groups()
            yield cls(directive.begin, directive.end, filename, code)


@union_rule(PreprocessorDirectives)
class IncludeFileDirectives(GenericPreprocessorDirectives["IncludeFileDirective"]):
    ...


@rule()
def _get_include_file_directives(request: PreprocessFileTarget) -> IncludeFileDirectives:
    content = get(ReadFile, ReadFileRequest(request.path)).content
    return IncludeFileDirectives(IncludeFileDirective.parse(content))


@rule()
def _include_file_request(request: IncludeFileDirective) -> RenderedDirective:
    code = f" code:{request.code}" if request.code else ""
    begin_marker = f"```{request.code}\n" if request.code else ""
    end_marker = "```\n" if request.code else ""
    return RenderedDirective(
        f"<!-- include {request.filename}{code} -->\n{begin_marker}"
        + Path(request.filename).read_text().strip()
        + f"\n{end_marker}<!-- end include -->"
    )


@dataclass(frozen=True)
@union_rule()
class TocDirective(PreprocessorDirective):
    path: Path

    @classmethod
    def parse(cls, path: Path, text: str) -> Iterator[TocDirective]:
        for directive in parse_directives(text, "table of contents"):
            yield cls(directive.begin, directive.end, path)


@union_rule(PreprocessorDirectives)
class TocDirectives(GenericPreprocessorDirectives["TocDirective"]):
    ...


@rule()
def _get_toc_directives(request: PreprocessFileTarget) -> TocDirectives:
    content = get(ReadFile, ReadFileRequest(request.path)).content
    return TocDirectives(TocDirective.parse(request.path, content))


@rule()
def _render_toc(request: TocDirective) -> RenderedDirective:
    content = get(ReadFile, ReadFileRequest(request.path)).content
    regex = re.compile(f"(#+)\\s+(.*)")
    matches = list(regex.finditer(content, request.end))
    min_depth = min(len(match.group(1)) for match in matches)
    toc = []
    for match in matches:
        depth = len(match.group(1)) - min_depth
        toc.append("  " * depth + f"* [{match.group(2)}](#{match.group(2).lower().replace(' ', '-')})")

    toc_string = "\n".join(toc)
    return RenderedDirective(f"<!-- table of contents -->\n{toc_string}\n<!-- end table of contents -->")


@dataclass
class PreviewGoal:
    ...


@rule()
def _preview_goal(ctx: Context) -> PreviewGoal:
    for file in ctx.select(PreprocessFileTarget):
        result = get(PreprocessFileResult, file)
        print()
        print("Preview", file.path, f"(replaced {result.num_directives} directive(s))")
        print("-" * 80)
        print(result.content)
        print("- " * 40)
    return PreviewGoal()


@dataclass
class PreprocessGoal:
    ...


@rule()
def _preprocess_goal(ctx: Context) -> PreprocessGoal:
    for file in ctx.select(PreprocessFileTarget):
        result = get(PreprocessFileResult, file)
        print("Update", file.path, f"(replaced {result.num_directives} directive(s))")
        file.path.write_text(result.content)
    return PreprocessGoal()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", choices=("update", "preview"), default="update")
    args = parser.parse_args()
    match args.goal:
        case "update":
            goal_type = PreprocessGoal
        case "preview":
            goal_type = PreviewGoal
        case _:
            parser.error(f"Unknown goal {args.goal!r}")

    ctx = Context()
    ctx << PreprocessFileTarget(path=Path("README.md"))
    engine = RuleEngine()
    engine.hashsupport.register(Context, id)
    engine.assert_(engine.graph)
    engine.assert_(ctx)
    engine.load_module(__name__)
    engine.get(goal_type, Params(ctx))
