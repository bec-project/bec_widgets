"""Module providing fuzzy search utilities for the BEC widgets."""

from __future__ import annotations

from typing import Any

from thefuzz import fuzz

FUZZY_SEARCH_THRESHOLD = 80


def is_match(
    text: str, row_data: dict[str, Any], relevant_keys: list[str], enable_fuzzy: bool
) -> bool:
    """
    Check if the text matches any of the relevant keys in the row data.

    Args:
        text (str): The text to search for.
        row_data (dict[str, Any]): The row data to search in.
        relevant_keys (list[str]): The keys to consider for searching.
        enable_fuzzy (bool): Whether to use fuzzy matching.
    Returns:
        bool: True if a match is found, False otherwise.
    """
    for key in relevant_keys:
        data = str(row_data.get(key, "") or "")
        if enable_fuzzy:
            match_ratio = fuzz.partial_ratio(text.lower(), data.lower())
            if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                return True
        else:
            if text.lower() in data.lower():
                return True
    return False
