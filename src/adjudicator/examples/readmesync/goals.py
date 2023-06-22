import logging
from dataclasses import dataclass

from adjudicator import get, rule

from .context import Context
from .targets import PreprocessFileResult, PreprocessFileTarget

logger = logging.getLogger(__name__)


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
        logger.info("Update %s (replaced %d directive(s))", file.path, result.num_directives)
        file.path.write_text(result.content)
    return PreprocessGoal()
