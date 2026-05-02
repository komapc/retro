"""Shared utilities used across tm.* modules."""


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# Source IDs that the orchestrator recognises as named-source cells.
# Ingest pipelines (GDELT, web_search) write to raw_ingest/{source}/{event}/;
# the orchestrator reads any directory name, but only these 13 get classified
# as a "site_search" cell in atlas state tracking.
KNOWN_SOURCE_IDS: list[str] = [
    "ynet", "haaretz", "haaretz_he", "toi", "globes", "reuters", "jpost",
    "israel_hayom", "walla", "n12", "maariv", "ch13", "kan11",
]
