"""Shared utilities used across tm.* modules."""


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# Source IDs the orchestrator recognises as named-source cells.
# Each entry must have a matching data/sources/{id}.json file.
KNOWN_SOURCE_IDS: list[str] = [
    "ynet", "haaretz", "haaretz_he", "toi", "globes", "reuters", "jpost",
    "israel_hayom", "walla", "n12", "maariv", "ch13", "kan11",
    "web_search", "gdelt",
]
