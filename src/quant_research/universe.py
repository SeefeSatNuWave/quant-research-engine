"""Load and validate the versioned research-universe definition."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


UNIVERSE_SCHEMA_VERSION = 1
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
_REQUIRED_TEXT_FIELDS = ("name", "industry", "source", "rationale")


class UniverseValidationError(ValueError):
    """Raised when a universe file violates the supported schema."""


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    name: str
    industry: str
    valid_from: date
    valid_to: date | None
    source: str
    rationale: str

    def is_valid_on(self, as_of: date) -> bool:
        """Return whether this effective-dated membership applies on ``as_of``."""
        return self.valid_from <= as_of and (self.valid_to is None or as_of < self.valid_to)


def _parse_date(value: Any, field: str, row_number: int) -> date:
    if not isinstance(value, str):
        raise UniverseValidationError(f"security {row_number}: {field} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise UniverseValidationError(
            f"security {row_number}: {field} must be an ISO date (YYYY-MM-DD)"
        ) from exc
    if parsed.isoformat() != value:
        raise UniverseValidationError(f"security {row_number}: {field} must use YYYY-MM-DD format")
    return parsed


def validate_universe(document: Any) -> tuple[UniverseMember, ...]:
    """Validate a parsed universe document and return immutable members.

    An empty ``securities`` list is valid as an unpopulated project template.
    ``valid_from`` is inclusive and ``valid_to`` is exclusive.
    """
    if not isinstance(document, dict):
        raise UniverseValidationError("universe document must be a JSON object")
    if set(document) != {"schema_version", "securities"}:
        raise UniverseValidationError("universe document must contain only schema_version and securities")
    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != UNIVERSE_SCHEMA_VERSION:
        raise UniverseValidationError(
            f"unsupported universe schema_version {schema_version!r}; "
            f"expected {UNIVERSE_SCHEMA_VERSION}"
        )
    securities = document.get("securities")
    if not isinstance(securities, list):
        raise UniverseValidationError("securities must be a JSON array")

    members: list[UniverseMember] = []
    seen: set[tuple[str, date]] = set()
    allowed = {"symbol", "name", "industry", "valid_from", "valid_to", "source", "rationale"}
    for row_number, item in enumerate(securities, start=1):
        if not isinstance(item, dict):
            raise UniverseValidationError(f"security {row_number} must be a JSON object")
        missing = {"symbol", "name", "industry", "valid_from", "source", "rationale"} - set(item)
        unknown = set(item) - allowed
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing fields: {', '.join(sorted(missing))}")
            if unknown:
                details.append(f"unknown fields: {', '.join(sorted(unknown))}")
            raise UniverseValidationError(f"security {row_number}: " + "; ".join(details))

        symbol = item["symbol"]
        if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
            raise UniverseValidationError(f"security {row_number}: symbol must be uppercase and ticker-like")
        for field in _REQUIRED_TEXT_FIELDS:
            value = item[field]
            if not isinstance(value, str) or not value.strip():
                raise UniverseValidationError(f"security {row_number}: {field} must be non-empty text")

        valid_from = _parse_date(item["valid_from"], "valid_from", row_number)
        valid_to_value = item.get("valid_to")
        valid_to = None if valid_to_value is None else _parse_date(valid_to_value, "valid_to", row_number)
        if valid_to is not None and valid_to <= valid_from:
            raise UniverseValidationError(f"security {row_number}: valid_to must be later than valid_from")
        key = (symbol, valid_from)
        if key in seen:
            raise UniverseValidationError(
                f"security {row_number}: duplicate membership for {symbol} starting {valid_from}"
            )
        seen.add(key)
        members.append(
            UniverseMember(
                symbol=symbol,
                name=item["name"].strip(),
                industry=item["industry"].strip(),
                valid_from=valid_from,
                valid_to=valid_to,
                source=item["source"].strip(),
                rationale=item["rationale"].strip(),
            )
        )

    by_symbol: dict[str, list[UniverseMember]] = {}
    for member in members:
        by_symbol.setdefault(member.symbol, []).append(member)
    for symbol, history in by_symbol.items():
        history.sort(key=lambda member: member.valid_from)
        for previous, following in zip(history, history[1:]):
            if previous.valid_to is None or following.valid_from < previous.valid_to:
                raise UniverseValidationError(f"overlapping effective-date ranges for {symbol}")
    return tuple(members)


def load_universe(path: str | Path) -> tuple[UniverseMember, ...]:
    """Read and validate a UTF-8 JSON universe document."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UniverseValidationError(f"could not read universe file {path}: {exc}") from exc
    return validate_universe(document)


def main() -> int:
    path = Path("configs/universe.json")
    members = load_universe(path)
    print(f"Validated {len(members)} universe membership row(s) from {path} (schema v{UNIVERSE_SCHEMA_VERSION}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
