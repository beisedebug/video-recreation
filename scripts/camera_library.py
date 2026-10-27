#!/usr/bin/env python3
"""Offline camera-card and attributed Seedance metadata lookup (stdlib only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


REFERENCES = Path(__file__).resolve().parent.parent / "references"
TYPES = ("camera_motion", "lens_motion", "static_view", "edit_effect")
SEARCH_NOTICE = (
    "仅按字面关键词检索候选，不是语义理解或推荐。不会可靠理解否定、先后顺序、"
    "时间范围或用户意图；例如‘不要环绕’仍可能命中 orbit。由主智能体结合对话确认选择。"
)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        self.exit(2)


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def read_reference(filename: str) -> dict:
    return json.loads((REFERENCES / filename).read_text(encoding="utf-8"))


def normalized(value: str) -> str:
    return " ".join(re.sub(r"[_\-]+", " ", value.casefold()).split())


def literal_match(query: str, term: str) -> bool:
    """Chinese substring or English word/phrase match, in either direction.

    This deliberately does not parse natural-language instructions. English
    boundaries prevent e.g. 'pan' from matching 'Japan'.
    """
    query, term = normalized(query), normalized(term)
    if not query or not term:
        return False

    def contains(haystack: str, needle: str) -> bool:
        if re.search(r"[\u3400-\u9fff]", needle):
            return needle in haystack
        return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack) is not None

    return contains(query, term) or contains(term, query)


def card_summary(card: dict) -> dict:
    return {key: card[key] for key in ("code", "id", "type", "name_zh", "human_effect")}


def card_matches(card: dict, query: str) -> list[str]:
    terms = [card["id"], card["code"], card["name_zh"]]
    terms.extend(card["keywords"]["zh"])
    terms.extend(card["keywords"]["en"])
    return list(dict.fromkeys(term for term in terms if literal_match(query, term)))


def main() -> int:
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list camera cards; no network calls")
    listing.add_argument("--type", choices=TYPES)
    search = commands.add_parser("search", help="literal keyword lookup; not semantic understanding")
    search.add_argument("query", nargs="+")
    search.add_argument("--type", choices=TYPES)
    search.add_argument("--limit", type=positive_int, default=15)
    show = commands.add_parser("show", help="show one complete card by id or Cxx code")
    show.add_argument("id")
    examples = commands.add_parser("examples", help="search attributed Seedance metadata, not full prompts")
    examples.add_argument("query", nargs="+")
    examples.add_argument("--limit", type=positive_int, default=20)
    args = parser.parse_args()

    try:
        if args.command == "examples":
            library = read_reference("seedance-index.json")
            query = " ".join(args.query).strip()
            if not query:
                parser.error("query must not be empty")
            matches = []
            for entry in library["entries"]:
                fields = [field for field in ("category", "title_zh", "author", "url")
                          if literal_match(query, str(entry.get(field) or ""))]
                if fields:
                    matches.append({**entry, "matched_fields": fields})
            result = {
                "query": query,
                "mode": "literal_metadata_lookup",
                "semantic_understanding": False,
                "notice": SEARCH_NOTICE,
                "source": library["source"],
                "assessment_notice": library["assessment_notice"],
                "total": len(matches),
                "count": min(len(matches), args.limit),
                "results": matches[:args.limit],
            }
        else:
            library = read_reference("camera-presets.json")
            cards = library["presets"]
            selected_type = getattr(args, "type", None)
            if selected_type:
                cards = [card for card in cards if card["type"] == selected_type]
            if args.command == "list":
                result = {"count": len(cards), "type_definitions": library["type_definitions"],
                          "results": [card_summary(card) for card in cards]}
            elif args.command == "show":
                card = next((card for card in cards if args.id.casefold() in
                             (card["id"].casefold(), card["code"].casefold())), None)
                if card is None:
                    parser.error(f"unknown preset id or code: {args.id}")
                result = card
            else:
                query = " ".join(args.query).strip()
                if not query:
                    parser.error("query must not be empty")
                matches = []
                for card in cards:
                    hits = card_matches(card, query)
                    if hits:
                        matches.append({**card_summary(card), "matched_keywords": hits})
                # Preserve catalogue order: the script makes no recommendation.
                result = {"query": query, "mode": "literal_keyword_lookup",
                          "semantic_understanding": False, "notice": SEARCH_NOTICE,
                          "total": len(matches), "count": min(len(matches), args.limit),
                          "results": matches[:args.limit]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": f"Unable to read camera library: {exc}"}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
