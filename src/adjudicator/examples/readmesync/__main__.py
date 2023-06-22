"""
ReadmeSync is a utility that allows you to place comments into a Markdown file that represent
directives for content to be included in their place. The following types of directives are
supported:

- `<!-- include <path> -->`: Include the contents of the file at the given path. A `code:<lang>`
    option can be added to the directive to wrap the content in a code block using the specified
    language name (can be empty).
- `<!-- runcmd <command> -->`: Run the given command and include the output in the document. A
    `code:<lang>` option can be added to the directive to wrap the output in a code block using
    the specified language name (can be empty).
- `<!-- table of contents -->`: Include a table of contents for the document for all Markdown
    headers following the directive.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from adjudicator import Params, RuleEngine

from .context import Context
from .goals import PreprocessGoal, PreviewGoal
from .targets import PreprocessFileTarget

logger = logging.getLogger(__name__)

modules = [
    "adjudicator.examples.readmesync." + x
    for x in [
        "goals",
        "readfile",
        "targets",
        "directives.generic",
        "directives.include",
        "directives.runcmd",
        "directives.toc",
    ]
]

parser = argparse.ArgumentParser(
    prog="python -m adjudicator.examples.readmesync",
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("file", default="README.md", nargs="?", help="[default: %(default)s]")
parser.add_argument("--preview", "-p", action="store_true", help="run in preview mode")
parser.add_argument("--verbose", "-v", action="store_true", help="enable verbose logging")


def main() -> None:
    args = parser.parse_args()
    goal_type = PreviewGoal if args.preview else PreprocessGoal
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="[%(asctime)s %(levelname)s] %(message)s"
    )

    ctx = Context()
    ctx << PreprocessFileTarget(path=Path(args.file))
    engine = RuleEngine()
    engine.hashsupport.register(Context, id)
    engine.assert_(engine.graph)
    engine.assert_(ctx)
    for module in modules:
        logger.debug("Loading module %s", module)
        engine.load_module(module)
    engine.get(goal_type, Params(ctx))


if __name__ == "__main__":
    main()
