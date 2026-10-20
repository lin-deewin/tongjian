#!/usr/bin/env python3
"""Check article evidence against the actual book, without interpreting its claims."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = re.compile(r"\[\[([^\]]+)\]\]")


def compact(value):
    return re.sub(r"\s+", "", value)


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)


def validate(path, cache):
    errors, warnings, evidence, quotation_checks = [], [], [], []
    try:
        article = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        return {"file": str(path.relative_to(ROOT)), "errors": [str(exc)]}
    for key in ("number", "slug", "title", "subtitle", "summary", "question", "blocks", "sources"):
        if key not in article:
            errors.append(f"Missing {key}")
    source_map = {}
    for source in article.get("sources", []):
        sid = source.get("id")
        if not sid or sid in source_map:
            errors.append(f"Duplicate or missing source id: {sid}")
        source_map[sid] = source
        try:
            number, year, index = source["volume"], source["year"], source["paragraph"]
            if not isinstance(number, int) or not 1 <= number <= 294 or year == 0 or index < 0:
                raise ValueError("Invalid volume, year, or index")
            if number not in cache:
                cache[number] = json.loads((ROOT / "dist" / f"volume{number}.json").read_text())
            record = next(y for y in cache[number]["years"] if y["year"] == year)
            paragraph = record["paragraphs"][index]
            text = "".join(r["text"] for r in paragraph.get("runs", []) if r.get("kind") == "text")
            note = "".join(r["text"] for r in paragraph.get("runs", []) if r.get("kind") == "note")
            kind = source.get("kind")
            if kind not in ("text", "note", "comment"):
                errors.append(f"{sid}: unsupported source kind {kind}")
            target = note if kind == "note" else text or paragraph.get("plain", "")
            excerpt = source.get("quote", "")
            matched = bool(excerpt) and compact(excerpt) in compact(target)
            evidence.append({"id": sid, "volume": number, "year": year, "paragraph": index,
                             "kind": kind, "exact_quote_match": matched,
                             "context_checked_by_author": source.get("context_checked") is True})
            if not matched:
                errors.append(f"{sid}: source quote not an exact contiguous match in {kind} runs")
            if source.get("context_checked") is not True:
                warnings.append(f"{sid}: no author context-check record")
            if not source.get("claim"):
                errors.append(f"{sid}: missing supported claim")
            source["_actual"] = target
        except (KeyError, StopIteration, IndexError, TypeError, ValueError) as exc:
            errors.append(f"{sid}: invalid source location ({exc})")
    used = set()
    heading_ids, figure_ids = set(), set()
    body, figure_count, kinds = [], 0, []
    for block_index, block in enumerate(article.get("blocks", [])):
        kind = block.get("type")
        for string in walk_strings(block):
            for sid in REF.findall(string):
                used.add(sid)
                if sid not in source_map:
                    errors.append(f"Block {block_index}: unknown reference {sid}")
        if kind in ("p", "h2", "h3", "quote"):
            body.append(block.get("text", ""))
        if kind in ("h2", "h3"):
            identity = block.get("id")
            if not identity or identity in heading_ids:
                errors.append(f"Missing or duplicate heading id: {identity}")
            heading_ids.add(identity)
        elif kind == "quote":
            sid = block.get("source")
            used.add(sid)
            exact = sid in source_map and compact(block.get("text", "")) in compact(source_map[sid].get("_actual", ""))
            quotation_checks.append({"block": block_index, "source": sid, "exact_match": exact})
            if not exact:
                errors.append(f"Block {block_index}: blockquote not exact in source {sid}")
        elif kind == "figure":
            figure_count += 1
            identity, graphic_kind = block.get("id"), block.get("kind")
            if not identity or identity in figure_ids:
                errors.append(f"Missing or duplicate figure id: {identity}")
            figure_ids.add(identity)
            kinds.append(graphic_kind)
            if not block.get("title") or not block.get("caption"):
                errors.append(f"Figure {identity}: missing title or explanatory caption")
            if graphic_kind == "flow":
                steps = block.get("steps", [])
                if not 3 <= len(steps) <= 5:
                    errors.append(f"Figure {identity}: expected 3–5 flow steps")
                if "links" in block and len(block["links"]) != len(steps) - 1:
                    errors.append(f"Figure {identity}: flow links do not match steps")
            elif graphic_kind == "comparison":
                columns = block.get("columns", [])
                if not 2 <= len(columns) <= 3:
                    errors.append(f"Figure {identity}: expected 2–3 comparison columns")
                for row in block.get("rows", []):
                    if len(row.get("cells", [])) != len(columns):
                        errors.append(f"Figure {identity}: comparison row has wrong cell count")
            elif graphic_kind == "timeline":
                if not 3 <= len(block.get("events", [])) <= 6:
                    errors.append(f"Figure {identity}: expected 3–6 timeline events")
            elif graphic_kind == "branches":
                if not block.get("prompt") or not 2 <= len(block.get("options", [])) <= 3:
                    errors.append(f"Figure {identity}: invalid branches")
            else:
                errors.append(f"Figure {identity}: unsupported kind {graphic_kind}")
        elif kind not in ("p", "h2", "h3"):
            errors.append(f"Block {block_index}: unsupported block type {kind}")
    text = "\n".join(body)
    chinese_chars = len(re.findall(r"[\u3400-\u9fff]", text))
    if chinese_chars < 3500:
        warnings.append(f"Body has {chinese_chars} Chinese characters; review depth against 4000–6000 target")
    if figure_count < 2:
        errors.append("Article requires at least two explanatory figures")
    unused = set(source_map) - used
    if unused:
        warnings.append(f"Sources not cited in body or figure: {', '.join(sorted(unused))}")
    # Editorial checks are still required: exact text does not establish claim validity.
    return {"file": str(path.relative_to(ROOT)), "number": article.get("number"),
            "title": article.get("title"), "chinese_body_characters": chinese_chars,
            "figures": figure_count, "figure_kinds": kinds, "sources": len(source_map),
            "evidence": evidence, "blockquote_checks": quotation_checks,
            "errors": errors, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/research-ten-topics/source-validation.json")
    args = parser.parse_args()
    paths = args.files or sorted((ROOT / "content/research-ten-topics").glob("[0-9][0-9]-*.json"))
    cache = {}
    articles = [validate(path.resolve(), cache) for path in paths]
    report = {"scope": "Source locations and exact excerpts only; historical interpretation independently reviewed.",
              "articles": articles, "article_count": len(articles),
              "errors": sum(len(a["errors"]) for a in articles),
              "warnings": sum(len(a.get("warnings", [])) for a in articles)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"articles": len(articles), "errors": report["errors"], "warnings": report["warnings"],
                      "report": str(args.output), "issues": [{"number": a.get("number"),
                       "errors": a["errors"], "warnings": a.get("warnings", [])}
                       for a in articles if a["errors"] or a.get("warnings")]}, ensure_ascii=False))
    raise SystemExit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
