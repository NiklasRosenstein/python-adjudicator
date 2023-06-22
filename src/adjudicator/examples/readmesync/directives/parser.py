import itertools
import logging
import re
from dataclasses import dataclass
from typing import Iterator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedDirective:
    begin: int
    end: int
    opts: str


def parse_directives(text: str, keyword: str) -> Iterator[ParsedDirective]:
    code_block_marker = re.compile(r"^```+\w*", re.M)
    code_blocks = [
        pair
        for idx, pair in enumerate(itertools.pairwise(m.start() for m in re.finditer(code_block_marker, text)))
        if idx % 2 == 0
    ]

    begin_regex = re.compile(r"<!--\s*" + re.escape(keyword) + r"(.*)?\s*-->")
    end_regex = re.compile(r"<!--\s*end\s*" + re.escape(keyword) + r"\s*-->")
    offset = 0

    def search(pattern: re.Pattern[str]) -> re.Match[str] | None:
        """
        Search for the given patern, but make sure it does not sit inside a code block.
        """

        match = pattern.search(text, offset)
        while match is not None:
            # Check if the match is between two code blocks.
            if any(match.start() in range(*pair) for pair in code_blocks):
                logger.debug(
                    "Skipping directive %r in [%d, %d] because it is inside a code block",
                    keyword,
                    match.start(),
                    match.end(),
                )
                match = pattern.search(text, match.end())
            else:
                break

        return match

    begin_match = search(begin_regex)
    while offset < len(text) and begin_match is not None:
        opts = begin_match.group(1).strip()
        begin = begin_match.start()
        offset = begin_match.end()
        end_match = search(end_regex)
        next_begin_match = search(begin_regex)

        if end_match is None or (next_begin_match and next_begin_match.start() < end_match.start()):
            end = begin_match.end()
            offset = begin_match.end()
        else:
            end = end_match.end()
            offset = end_match.end()

        logger.debug("Found directive %r in [%d, %d]", keyword, begin, end)
        yield ParsedDirective(begin, end, opts)

        begin_match = next_begin_match
