"""Convert text typed by the user into Python objects.

Accepted formats
----------------
Set:      {1, 2, 3}      {apple, 2, x}      {}  (the empty set)
Mapping:  1->a, 2->b, 3->a        (an empty line means "no pairs")

Element rule
------------
A token made of the ASCII digits 0-9, with an optional leading + or -
(``7``, ``-3``, ``+5``), becomes an ``int``; anything else stays a
``str``. Without this rule "2" typed in one set and "2" typed in
another could be compared as different types. Digits from other
scripts (for example the Bengali ৩) are treated as words.

Nested sets and tuples are NOT accepted as input; elements are plain
numbers or words. (The program still *produces* nested results, such
as power sets, internally.)

Every problem raises ``ParseError`` with a message that tells the user
what to fix.
"""

from __future__ import annotations

import re
from typing import Hashable, List, NamedTuple, Tuple, Union

from toolkit.exceptions import ParseError

__all__ = ["ParsedSet", "parse_element", "parse_set", "parse_mapping"]

# Only the ASCII digits 0-9 count. (Python's \d would also accept digits
# from other scripts, such as the Bengali ৩, and silently turn them into
# numbers; restricting to 0-9 keeps the rule simple and predictable.)
_INTEGER = re.compile(r"[+-]?[0-9]+")
_RESERVED = set("{}(),")

# Matches Python's own default limit for converting text to int.
MAX_INTEGER_DIGITS = 4300


class ParsedSet(NamedTuple):
    """The parsed set plus any elements the user typed more than once."""

    elements: frozenset
    duplicates: Tuple[Hashable, ...]


def parse_element(token: str) -> Union[int, str]:
    """Turn one token such as ``'7'`` or ``'apple'`` into an element."""
    token = token.strip()
    if not token:
        raise ParseError("an element is empty (check for an extra comma)")
    if any(ch in _RESERVED for ch in token) or "->" in token:
        raise ParseError(
            f"'{token}' is not a valid element: use plain numbers or "
            f"words, without braces {{ }}, parentheses ( ), commas or '->'"
        )
    if any(ch.isspace() for ch in token):
        raise ParseError(
            f"'{token}' contains a space: did you forget a comma between "
            f"elements?"
        )
    if _INTEGER.fullmatch(token):
        # Recent Python versions refuse to convert integers with more than
        # 4300 digits and raise ValueError. We check the length ourselves
        # so the behaviour is identical on every Python version, and still
        # catch ValueError as a safety net.
        too_long = ParseError(
            f"the number starting {token[:12]}... has {len(token)} "
            f"characters; numbers may have at most {MAX_INTEGER_DIGITS} digits"
        )
        if len(token.lstrip("+-")) > MAX_INTEGER_DIGITS:
            raise too_long
        try:
            return int(token)
        except ValueError:
            raise too_long from None
    return token


def parse_set(text: str) -> ParsedSet:
    """Parse ``'{1, 2, 2, x}'`` into ``ParsedSet({1, 2, 'x'}, (2,))``."""
    text = text.strip()
    if not text:
        raise ParseError("no set was entered; write it like {1, 2, 3}")
    if not (text.startswith("{") and text.endswith("}")):
        raise ParseError("a set must be written in braces, e.g. {1, 2, 3}")

    body = text[1:-1].strip()
    if not body:
        return ParsedSet(frozenset(), ())

    seen: List[Hashable] = []
    duplicates: List[Hashable] = []
    for token in body.split(","):
        element = parse_element(token)
        if element in seen:
            if element not in duplicates:
                duplicates.append(element)
        else:
            seen.append(element)
    return ParsedSet(frozenset(seen), tuple(duplicates))


def parse_mapping(text: str) -> List[Tuple[Hashable, Hashable]]:
    """Parse ``'1->a, 2->b'`` into ``[(1, 'a'), (2, 'b')]``.

    The result is a *list of pairs*, not a dict, so that a conflicting
    mapping such as ``1->a, 1->b`` reaches the Function validator intact
    instead of being silently overwritten.
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1].strip()
    if not text:
        return []

    pairs = []
    for item in text.split(","):
        item = item.strip()
        if item.count("->") != 1:
            raise ParseError(
                f"'{item}' is not a mapping; write each pair as input->output, "
                f"e.g. 1->a"
            )
        left, right = item.split("->")
        if not left.strip() or not right.strip():
            raise ParseError(f"'{item}' is missing an input or an output")
        pairs.append((parse_element(left), parse_element(right)))
    return pairs
