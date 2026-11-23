"""Pure parsers that turn raw Zomato listings into catalog restaurants."""

from __future__ import annotations

import ast
import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import ftfy

from app.catalog.models import Restaurant

DISH_CAP = 12
SNIPPET_CAP = 2
SNIPPET_LENGTH = 280
ID_LENGTH = 12
LONG_REVIEW_THRESHOLD = 100_000
_BODY_SCAN_LIMIT = 400

_WHITESPACE = re.compile(r"\s+")
_RATED_PREFIX = re.compile(r"^RATED\s*", re.IGNORECASE)
_ESCAPE_MAP = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "v": "\v",
}


@dataclass
class CleanedListing:
    """One source listing after parsing, before duplicate merge."""

    name: str
    address: str
    location: str
    cuisines: list[str]
    cost_for_two: int | None
    rating: float | None
    votes: int
    rest_types: list[str]
    dishes_liked: list[str]
    online_order: bool
    book_table: bool
    listed_types: list[str]
    review_snippets: list[str]
    url: str
    normalized_name: str
    normalized_address: str


@dataclass
class MergeStats:
    restaurants: list[Restaurant] = field(default_factory=list)
    dropped: int = 0


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def parse_rating(value: object) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        rating = float(value)
        return rating if 0 <= rating <= 5 else None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.casefold()
    if lowered == "new" or text == "-":
        return None
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    try:
        rating = float(text)
    except ValueError:
        return None
    if 0 <= rating <= 5:
        return rating
    return None


def parse_cost(value: object) -> int | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if not value.is_integer() or value <= 0:
            return None
        return int(value)
    text = re.sub(r"[,\s]", "", str(value))
    if not text:
        return None
    try:
        cost = int(text)
    except ValueError:
        return None
    return cost if cost > 0 else None


def parse_votes(value: object) -> int:
    if _is_missing(value):
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, float):
        if not value.is_integer() or value <= 0:
            return 0
        return int(value)
    text = re.sub(r"[,\s]", "", str(value).strip())
    if not text:
        return 0
    try:
        votes = int(text)
    except ValueError:
        return 0
    return votes if votes > 0 else 0


def split_list(value: object) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, (list, tuple)):
        tokens = [str(item).strip() for item in value]
    else:
        tokens = str(value).split(",")
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def parse_yes_no(value: object) -> bool:
    if _is_missing(value):
        return False
    return str(value).strip().casefold() == "yes"


def fix_text(value: object) -> str:
    if _is_missing(value):
        return ""
    text = ftfy.fix_text(str(value))
    return _WHITESPACE.sub(" ", text).strip()


def extract_snippets(value: object) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, (list, tuple)):
        return _snippets_from_pairs(value)
    text = str(value)
    if not text.strip():
        return []
    if len(text) > LONG_REVIEW_THRESHOLD:
        return _snippets_from_pairs(_scan_review_pairs(text, limit=SNIPPET_CAP))
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError, MemoryError, TypeError):
        return []
    if not isinstance(parsed, (list, tuple)):
        return []
    return _snippets_from_pairs(parsed)


def normalize_identity(name: object, address: object) -> tuple[str, str]:
    return _normalize_part(name), _normalize_part(address)


def make_id(name: object, address: object) -> str:
    normalized_name, normalized_address = normalize_identity(name, address)
    payload = f"{normalized_name}\n{normalized_address}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:ID_LENGTH]


def merge_listings(rows: Iterable[Mapping[str, Any]]) -> list[Restaurant]:
    return merge_with_stats(rows).restaurants


def merge_with_stats(rows: Iterable[Mapping[str, Any]]) -> MergeStats:
    groups: dict[tuple[str, str], list[CleanedListing]] = {}
    dropped = 0
    for row in rows:
        listing = clean_listing(row)
        if not listing.normalized_name or not listing.normalized_address:
            dropped += 1
            continue
        key = (listing.normalized_name, listing.normalized_address)
        groups.setdefault(key, []).append(listing)
    restaurants = [_merge_group(group) for group in groups.values()]
    return MergeStats(restaurants=restaurants, dropped=dropped)


def clean_listing(row: Mapping[str, Any]) -> CleanedListing:
    name = fix_text(row.get("name"))
    address = fix_text(row.get("address"))
    normalized_name, normalized_address = normalize_identity(name, address)
    return CleanedListing(
        name=name,
        address=address,
        location=fix_text(row.get("location")),
        cuisines=split_list(row.get("cuisines")),
        cost_for_two=parse_cost(row.get("approx_cost(for two people)")),
        rating=parse_rating(row.get("rate")),
        votes=parse_votes(row.get("votes")),
        rest_types=split_list(row.get("rest_type")),
        dishes_liked=split_list(row.get("dish_liked")),
        online_order=parse_yes_no(row.get("online_order")),
        book_table=parse_yes_no(row.get("book_table")),
        listed_types=split_list(row.get("listed_in(type)")),
        review_snippets=extract_snippets(row.get("reviews_list")),
        url="" if _is_missing(row.get("url")) else str(row.get("url")).strip(),
        normalized_name=normalized_name,
        normalized_address=normalized_address,
    )


def _normalize_part(value: object) -> str:
    return _WHITESPACE.sub(" ", fix_text(value).casefold()).strip()


def _snippets_from_pairs(pairs: object) -> list[str]:
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)):
        return []
    snippets: list[str] = []
    for pair in pairs:
        if len(snippets) >= SNIPPET_CAP:
            break
        body = _review_body(pair)
        if body:
            snippets.append(body)
    return snippets


def _review_body(pair: object) -> str | None:
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return None
    raw = pair[1]
    if _is_missing(raw):
        return None
    text = _RATED_PREFIX.sub("", str(raw), count=1)
    text = _WHITESPACE.sub(" ", text).strip()
    if not text:
        return None
    return text[:SNIPPET_LENGTH]


def _scan_review_pairs(text: str, limit: int = SNIPPET_CAP) -> list[tuple[str, str]]:
    """Pull the first review tuples from a huge literal without parsing it whole."""
    pairs: list[tuple[str, str]] = []
    index = 0
    length = len(text)
    while index < length and len(pairs) < limit:
        start = text.find("(", index)
        if start == -1:
            break
        cursor = start + 1
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] not in {"'", '"'}:
            index = start + 1
            continue
        first, cursor = _read_python_string(text, cursor, collect_limit=32)
        if first is None or not first.startswith("Rated"):
            index = start + 1
            continue
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] != ",":
            index = start + 1
            continue
        cursor += 1
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] not in {"'", '"'}:
            index = start + 1
            continue
        second, cursor = _read_python_string(text, cursor, collect_limit=_BODY_SCAN_LIMIT)
        if second is None:
            index = start + 1
            continue
        pairs.append((first, second))
        index = cursor
    return pairs


def _read_python_string(text: str, start: int, collect_limit: int) -> tuple[str | None, int]:
    quote = text[start]
    index = start + 1
    length = len(text)
    chars: list[str] = []
    collected = 0
    while index < length:
        char = text[index]
        if char == "\\":
            if index + 1 >= length:
                return None, start + 1
            decoded = _ESCAPE_MAP.get(text[index + 1], text[index + 1])
            if collected < collect_limit:
                chars.append(decoded)
                collected += 1
            index += 2
            continue
        if char == quote:
            return "".join(chars), index + 1
        if collected < collect_limit:
            chars.append(char)
            collected += 1
        index += 1
    return None, start + 1


def _merge_group(group: list[CleanedListing]) -> Restaurant:
    winner = max(group, key=lambda item: (item.votes, item.rating is not None))
    snippets: list[str] = []
    for listing in group:
        for snippet in listing.review_snippets:
            if len(snippets) >= SNIPPET_CAP:
                break
            snippets.append(snippet)
        if len(snippets) >= SNIPPET_CAP:
            break
    return Restaurant(
        id=make_id(winner.name, winner.address),
        name=winner.name,
        address=winner.address,
        location=winner.location,
        cuisines=_union_lists(listing.cuisines for listing in group),
        cost_for_two=winner.cost_for_two,
        rating=winner.rating,
        votes=winner.votes,
        rest_types=_union_lists(listing.rest_types for listing in group),
        dishes_liked=_union_lists((listing.dishes_liked for listing in group), cap=DISH_CAP),
        online_order=winner.online_order,
        book_table=winner.book_table,
        listed_types=_union_lists(listing.listed_types for listing in group),
        review_snippets=snippets,
        url=winner.url,
    )


def _union_lists(groups: Iterable[list[str]], cap: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for items in groups:
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
            if cap is not None and len(result) >= cap:
                return result
    return result
