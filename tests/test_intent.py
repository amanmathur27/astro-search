from astro_search.intent import classify

CASES = [
    ("next lunar eclipse", "celestial_event_lookup"),
    ("when is the next solar eclipse visible from India", "celestial_event_detail"),
    ("aurora forecast tonight", "current_phenomenon"),
    ("Kp index right now", "current_phenomenon"),
    ("latest James Webb discoveries", "recent_news"),
    ("papers on dark matter arxiv", "research_lookup"),
    ("distance to Andromeda galaxy", "object_lookup"),
    ("where is voyager now mission status", "mission_status"),
    ("all meteor showers calendar 2026", "periodic_event"),
    ("what is a pulsar", "concept_explanation"),
    ("phase of moon today", "celestial_event_lookup"),
    ("Perseid meteor shower 2026 peak date", "celestial_event_lookup"),
    ("who is in space right now", "mission_status"),
    ("size of Jupiter", "object_lookup"),
    ("explain black hole", "concept_explanation"),
]

def test_intents():
    for q, exp in CASES:
        got, _ = classify(q)
        assert got == exp, f"{q!r}: got {got}, want {exp}"
