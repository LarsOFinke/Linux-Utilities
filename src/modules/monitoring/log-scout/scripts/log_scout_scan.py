"""Build one bounded triage snapshot from independently readable sources."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from log_scout_rules import CATEGORIES, classify, sanitize, signature
from log_scout_sources import MAX_FILES, read_file, read_journal


def scan(files: list[Path], journal: bool, since: str, limit: int) -> dict:
    if not 1 <= limit <= 10000 or len(files) > MAX_FILES:
        raise ValueError("Use 1–10000 entries per source and at most 16 text logs")
    if not since.strip() or len(since) > 128:
        raise ValueError("--since must be a nonempty journal time expression (at most 128 characters)")
    now = datetime.now(timezone.utc)
    result = {"schema_version": 1, "rules_version": 1,
              "id": now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8],
              "created_at": now.isoformat(), "partial": False, "examined": 0, "matches": 0,
              "categories": dict.fromkeys(CATEGORIES, 0), "groups": [], "sources": [],
              "omitted_matches": 0, "options": {"since": sanitize(since), "limit_per_source": limit}}
    sources = [("journal", lambda: read_journal(limit, since))] if journal else []
    for path in dict.fromkeys(files):
        sources.append((str(path), lambda path=path: read_file(path, limit)))
    if not sources:
        raise ValueError("Select the journal or at least one text log")
    groups = {}
    successes = 0
    for name, read in sources:
        source = {"name": sanitize(name, 512), "examined": 0, "warnings": [], "error": ""}
        result["sources"].append(source)
        try:
            records, warnings = read()
        except (OSError, ValueError, RuntimeError) as error:
            source["error"] = sanitize(error, 1000)
            result["partial"] = True
            continue
        successes += 1
        source["warnings"] = [sanitize(warning, 1000) for warning in warnings]
        result["partial"] |= bool(warnings)
        source["examined"] = len(records)
        result["examined"] += len(records)
        for record in records:
            unit = str(record["unit"])
            finding = classify(record["message"], record["priority"], unit)
            if finding is None:
                continue
            category, severity = finding
            result["matches"] += 1
            result["categories"][category] += 1
            message = sanitize(record["message"])
            pattern = signature(message)
            unit = sanitize(unit, 200)
            key = (category, severity, source["name"], unit, pattern)
            if key not in groups:
                if len(groups) >= 250:
                    result["omitted_matches"] += 1
                    result["partial"] = True
                    continue
                groups[key] = {"category": category, "severity": severity, "source": source["name"],
                               "unit": unit, "pattern": pattern, "count": 0, "examples": []}
            group = groups[key]
            group["count"] += 1
            if len(group["examples"]) < 2:
                group["examples"].append({"message": message, "timestamp": sanitize(record["timestamp"], 100)})
    if not successes:
        errors = "; ".join(f"{s['name']}: {s['error']}" for s in result["sources"])
        raise RuntimeError(f"No source could be read; previous cache preserved. {errors}")
    severity_order = {"critical": 0, "error": 1, "warning": 2}
    result["groups"] = sorted(groups.values(), key=lambda g: (severity_order[g["severity"]], -g["count"], g["pattern"]))
    return result
