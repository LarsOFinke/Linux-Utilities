"""Terminal summary, paged categories, and representative finding details."""

from __future__ import annotations

from log_scout_rules import CATEGORIES, sanitize


def summary(scan: dict) -> None:
    print(f"Scan {scan['id']} — {scan['created_at']}")
    print(f"Examined {scan['examined']} entries; {scan['matches']} warning/error matches.")
    print("Coverage: partial (see below)" if scan["partial"] else "Coverage: selected readable sources within configured bounds")
    for index, (category, label) in enumerate(CATEGORIES.items(), 1):
        print(f"  {index}. {category:<10} {scan['categories'][category]:>6}  {label}")
    for source in scan["sources"]:
        print(f"Source: {sanitize(source['name'])} ({source['examined']} entries)")
        if source["error"]:
            print(f"  Unreadable: {sanitize(source['error'])}")
        for warning in source["warnings"]:
            print(f"  Coverage note: {sanitize(warning)}")
    if scan["omitted_matches"]:
        print(f"Detail cap: {scan['omitted_matches']} matches counted without examples (250 group limit).")
    print("Heuristic triage, not a health verdict. Access permissions can hide additional logs.")


def category_groups(scan: dict, category: str) -> list[dict]:
    return [group for group in scan["groups"] if group["category"] == category]


def group_details(group: dict) -> None:
    print(f"{group['severity'].upper()} — {group['count']} occurrences")
    print(f"Source: {sanitize(group['source'])}; unit: {sanitize(group['unit']) or 'unspecified'}")
    print(f"Pattern: {sanitize(group['pattern'])}")
    print("Representative examples (up to two; journal timestamps are epoch microseconds):")
    for example in group["examples"]:
        print(f"  {sanitize(example['timestamp']) or 'time in message / unavailable'}: {sanitize(example['message'])}")


def details(scan: dict, category: str, offset: int = 0, limit: int = 20, group: int | None = None) -> None:
    groups = category_groups(scan, category)
    if group is not None:
        if not 1 <= group <= len(groups):
            raise ValueError(f"Group must be between 1 and {len(groups)} for {category}")
        group_details(groups[group - 1])
        return
    print(f"{CATEGORIES[category]}: {scan['categories'][category]} matches; {len(groups)} cached groups")
    if not groups:
        print("No cached examples in this category.")
    for index, item in enumerate(groups[offset:offset + limit], offset + 1):
        print(f"  {index}. [{item['severity']}] {item['count']}× {sanitize(item['pattern'], 150)}")
    if offset + limit < len(groups):
        print(f"More groups: use --offset {offset + limit}; select details with --group NUMBER")


def browse(scan: dict) -> None:
    categories = list(CATEGORIES)
    while True:
        try:
            choice = input("Category name/number, or q to finish: ").strip().lower()
        except EOFError:
            return
        if choice in ("q", "quit", ""):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(categories):
            choice = categories[int(choice) - 1]
        if choice not in CATEGORIES:
            print("Select a listed category or q.")
            continue
        offset = 0
        while True:
            details(scan, choice, offset)
            try:
                action = input("Group number, n/p for page, b for categories, q to finish: ").strip().lower()
            except EOFError:
                return
            if action in ("q", "quit"):
                return
            if action in ("b", ""):
                break
            groups = category_groups(scan, choice)
            if action == "n":
                if offset + 20 < len(groups):
                    offset += 20
            elif action == "p":
                offset = max(0, offset - 20)
            elif action.isdigit() and 1 <= int(action) <= len(groups):
                group_details(groups[int(action) - 1])
            else:
                print("Select a listed group number, n, p, b, or q.")
