"""Apply complete translation replacements to a canonical volume.

The replacement files are deliberately separate from ``volumeN.json``.  A
replacement may change the translation groups, but it must bind itself to the
exact canonical volume and to the exact paragraph sequence for every year.
This module is also used by the full-book validator, so it is intentionally
strict about those bindings.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


BAIYANG_MARKER = re.compile(r"柏杨\s*曰")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def paragraph_plain(paragraph: dict[str, Any]) -> str:
    """Return the source text used for a stable paragraph fingerprint."""
    if "plain" in paragraph:
        return str(paragraph["plain"])
    return "".join(
        str(run.get("text", ""))
        for run in paragraph.get("runs", [])
        if run.get("kind") == "text"
    )


def paragraph_sha256(paragraph: dict[str, Any]) -> str:
    return hashlib.sha256(paragraph_plain(paragraph).encode("utf-8")).hexdigest()


def paragraph_hashes(year: dict[str, Any]) -> list[str]:
    return [paragraph_sha256(p) for p in year.get("paragraphs", [])]


def paragraph_signature(year: dict[str, Any]) -> str:
    """Return the canonical per-year signature used by replacement files.

    This deliberately mirrors ``JSON.stringify(y.paragraphs)`` in the
    browser and ``json.dumps(..., ensure_ascii=False, separators=(',', ':'))``
    in the importer.  Hashing the serialized paragraph objects binds runs,
    kinds, and source text, rather than only the extracted plain strings.
    """
    value = json.dumps(
        year.get("paragraphs", []),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValueError(f"{label} must be a SHA256 hex digest")


def _year_entries(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    entries = overlay.get("years")
    if not isinstance(entries, list):
        raise ValueError("replacement years must be a list")
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("replacement year entries must be objects")
    return entries


def _signature_value(entry: dict[str, Any], overlay: dict[str, Any], year: dict[str, Any]) -> Any:
    """Accept the published per-year list or its compact digest form.

    The list form is useful for diagnostics and catches a changed paragraph at
    its exact index.  The compact string is accepted for future generated
    files and is the digest returned by :func:`paragraph_signature`.
    """
    for key in ("sourceParagraphSHA256", "sourceParagraphsSHA256", "paragraphSHA256"):
        if key in entry:
            return entry[key]
    top = overlay.get("sourceParagraphSHA256")
    if isinstance(top, dict):
        return top.get(str(year["year"]), top.get(year["year"]))
    return None


def _validate_source_signature(
    entry: dict[str, Any], overlay: dict[str, Any], year: dict[str, Any]
) -> None:
    value = _signature_value(entry, overlay, year)
    if value is None:
        raise ValueError(f"replacement year {year['year']} has no source paragraph signature")
    actual = paragraph_hashes(year)
    if isinstance(value, list):
        if value != actual:
            raise ValueError(f"source paragraph hashes changed in year {year['year']}")
    elif isinstance(value, dict):
        expected = {str(i): digest for i, digest in enumerate(actual)}
        if value != expected:
            raise ValueError(f"source paragraph hash map changed in year {year['year']}")
    elif isinstance(value, str):
        _assert_digest(value, f"sourceParagraphSHA256 for year {year['year']}")
        if value != paragraph_signature(year):
            raise ValueError(f"source paragraph signature changed in year {year['year']}")
    else:
        raise ValueError(f"invalid source paragraph signature in year {year['year']}")


def _contains_baiyang(value: Any) -> bool:
    if isinstance(value, str):
        return bool(BAIYANG_MARKER.search(value))
    if isinstance(value, dict):
        return any(_contains_baiyang(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_baiyang(v) for v in value)
    return False


def _clean_headers(value: Any) -> Any:
    """Remove commentary headers which are themselves 柏杨曰 labels."""
    if isinstance(value, list):
        return [item for item in value if not _contains_baiyang(item)]
    if isinstance(value, str) and _contains_baiyang(value):
        return ""
    return value


def _validate_group(group: dict[str, Any], year: dict[str, Any], seen: set[int]) -> bool:
    if not isinstance(group, dict):
        raise ValueError(f"year {year['year']} has a non-object bilingual group")
    if _contains_baiyang(group.get("modern", "")) or _contains_baiyang(
        group.get("sourceOriginal", "")
    ):
        # The caller drops the whole group.  Returning False keeps this helper
        # safe even if an importer accidentally emitted a commentary group.
        return False
    modern = group.get("modern")
    if not isinstance(modern, str) or not modern.strip():
        raise ValueError(f"year {year['year']} has an empty translation")
    indices = group.get("huIndices", [])
    difference = bool(group.get("difference"))
    if not isinstance(indices, list) or any(not isinstance(i, int) for i in indices):
        raise ValueError(f"year {year['year']} has invalid huIndices")
    if difference and indices:
        raise ValueError(f"difference group in year {year['year']} has huIndices")
    if not difference and not indices:
        raise ValueError(f"matched group in year {year['year']} has no huIndices")
    for index in indices:
        if index < 0 or index >= len(year.get("paragraphs", [])):
            raise ValueError(f"year {year['year']} huIndex out of range: {index}")
        if index in seen:
            raise ValueError(f"year {year['year']} has duplicate huIndex: {index}")
        seen.add(index)
    return True


def _validate_year_entry(
    entry: dict[str, Any], overlay: dict[str, Any], year: dict[str, Any]
) -> dict[str, Any]:
    if entry.get("year") != year.get("year"):
        raise ValueError(f"replacement year mismatch: {entry.get('year')} != {year.get('year')}")
    _validate_source_signature(entry, overlay, year)
    groups = entry.get("bilingual", [])
    if not isinstance(groups, list):
        raise ValueError(f"replacement bilingual for year {year['year']} must be a list")
    seen: set[int] = set()
    kept: list[dict[str, Any]] = []
    for group in groups:
        if _validate_group(group, year, seen):
            kept.append(copy.deepcopy(group))
    calculated_missing = sorted(set(range(len(year.get("paragraphs", [])))) - seen)
    supplied_missing = entry.get("translationMissing", calculated_missing)
    if not isinstance(supplied_missing, list) or supplied_missing != calculated_missing:
        raise ValueError(f"translationMissing mismatch in year {year['year']}")
    out = dict(
        bilingual=kept,
        translationMissing=calculated_missing,
        translationHeaders=_clean_headers(entry.get("translationHeaders", [])),
        translationWarning=entry.get("translationWarning", ""),
    )
    if "yearIllustrations" in entry:
        out["yearIllustrations"] = copy.deepcopy(entry["yearIllustrations"])
    return out


def apply(
    book: dict[str, Any],
    overlay: dict[str, Any],
    *,
    canonical_sha: str | None = None,
) -> dict[str, Any]:
    """Replace all translation fields in ``book`` after validating bindings.

    ``canonical_sha`` should be supplied by :func:`load_replacement`, which
    can hash the original file bytes.  Keeping the argument explicit prevents
    an object re-serialization from being mistaken for the canonical digest.
    """
    if overlay.get("schemaVersion") != 1:
        raise ValueError("unsupported translation replacement schema")
    if overlay.get("volume") != book.get("volume"):
        raise ValueError("translation replacement volume mismatch")
    base = overlay.get("baseSHA256")
    _assert_digest(base, "baseSHA256")
    if canonical_sha is not None and base != canonical_sha:
        raise ValueError(f"canonical volume SHA256 mismatch for volume {book.get('volume')}")
    source = overlay.get("sourceSHA256", overlay.get("translationEpubSHA256"))
    _assert_digest(source, "sourceSHA256")

    entries = _year_entries(overlay)
    by_year = {year.get("year"): year for year in book.get("years", [])}
    if len(by_year) != len(book.get("years", [])):
        raise ValueError("canonical book has duplicate years")
    if {entry.get("year") for entry in entries} != set(by_year):
        raise ValueError("replacement years do not exactly cover the canonical volume")

    result = copy.deepcopy(book)
    replacement_by_year = {entry["year"]: entry for entry in entries}
    for year in result["years"]:
        values = _validate_year_entry(replacement_by_year[year["year"]], overlay, year)
        year.update(values)
        # These counters are translation metadata, and stale supplement
        # counters must not survive a complete replacement.
        year.pop("translationSupplemented", None)
        year.pop("translationRecovered", None)
    if "translationSource" in overlay:
        result["translationSource"] = overlay["translationSource"]
    result["translationReplacement"] = {
        "schemaVersion": 1,
        "sourceSHA256": source,
    }
    return result


def load_replacement(
    book_path: Path, replacement_path: Path
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Load canonical book and replacement, checking its raw-byte binding."""
    book_raw = book_path.read_bytes()
    digest = hashlib.sha256(book_raw).hexdigest()
    book = json.loads(book_raw.decode("utf-8"))
    overlay = json.loads(replacement_path.read_text(encoding="utf-8"))
    # apply() performs all structural checks and the digest check below binds
    # it to the exact bytes that were read.
    apply(book, overlay, canonical_sha=digest)
    return book, overlay, digest


def replacement_path(data_dir: Path, volume: int) -> Path:
    return data_dir / "translation-replacements" / f"volume{volume}.json"
