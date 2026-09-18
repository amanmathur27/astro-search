"""Bounded rapid-report discovery; not a measurement or confirmation service."""
import re
from .relevance import tokens

PROVIDER = re.compile(r"\b(?:atel|astronomer['’]?s telegram)\b", re.I)
TOPIC = re.compile(r"\b(?:grb|gamma[ -]ray bursts?|supernovae?|novae?|blazars?|astronomical transients?)\b", re.I)
IDENTIFIER = re.compile(r"\b(?:ATel\s*#?\s*\d+|GRB\s*\d{6}[A-Z]?)\b", re.I)


def is_alert_query(query):
    if re.search(r"\b(?:papers?|arxiv|preprints?|journals?|explain|define)\b|\bwhat (?:is|are)\b", query, re.I):
        return False
    return bool(PROVIDER.search(query) or
                (TOPIC.search(query) and (IDENTIFIER.search(query) or re.search(
                    r"\b(?:alerts?|reports?|follow[ -]up|detected|discovered)\b", query, re.I))))


def report_matches(query, title, summary):
    """Require all residual query terms; provider/browse words are not content."""
    blob = title + ' ' + summary
    for match in IDENTIFIER.finditer(query):
        compact = re.sub(r"[\s#]", "", match.group()).lower()
        if compact not in {re.sub(r"[\s#]", "", m.group()).lower() for m in IDENTIFIER.finditer(blob)}:
            return False
    q = IDENTIFIER.sub('', PROVIDER.sub('', query))
    q = re.sub(r"\b(?:latest|recent|new|astronomical|transients?|alerts?|reports?|updates?|today|follow[ -]up)\b", '', q, flags=re.I)
    return tokens(q) <= tokens(blob)
