import json
import re

def load_keywords(path="keywords.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _pattern_matches(text_lower, entry):
    pattern = entry["pattern"]
    match_type = entry["match_type"]

    if match_type == "substring":
        return pattern.lower() in text_lower
    elif match_type == "whole_word":
        regex = r"\b" + re.escape(pattern) + r"\b"
        return re.search(regex, text_lower, re.IGNORECASE) is not None
    elif match_type == "regex":
        return re.search(pattern, text_lower, re.IGNORECASE) is not None
    else:
        return False

def check_message(text, keywords=None):
    """
    Returns a dict: {"matched": [...], "excluded_by": [...] } 
    If excluded_by is non-empty, the message should NOT be forwarded.
    If matched is empty, no positive keyword hit.
    """
    if keywords is None:
        keywords = load_keywords()

    text_lower = text.lower()
    matched = []
    excluded_by = []

    for entry in keywords:
        if not entry.get("enabled", True):
            continue
        if _pattern_matches(text_lower, entry):
            if entry.get("exclusion", False):
                excluded_by.append(entry["pattern"])
            else:
                matched.append({"pattern": entry["pattern"], "category": entry["category"]})

    return {"matched": matched, "excluded_by": excluded_by}


if __name__ == "__main__":
    # Quick manual test
    test_messages = [
        "Anyone know the deadline for the visa application?",
        "This is urgent, please respond ASAP",
        "This is urgent just kidding, no rush",
        "IPO allotment status is out today",
        "Random unrelated message",
    ]
    for msg in test_messages:
        result = check_message(msg)
        print(f"MSG: {msg}")
        print(f"  -> {result}")
        print()
