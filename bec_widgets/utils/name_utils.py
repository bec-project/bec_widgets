import re


def pascal_to_snake(name: str) -> str:
    """
    Convert PascalCase to snake_case.

    Args:
        name (str): The name to be converted.

    Returns:
        str: The converted name.
    """
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return s2.lower()


def sanitize_namespace(namespace: str | None) -> str | None:
    """
    Clean user-provided namespace labels for filesystem compatibility.

    Args:
        namespace (str | None): Arbitrary namespace identifier supplied by the caller.

    Returns:
        str | None: Sanitized namespace containing only safe characters, or ``None``
            when the input is empty.
    """
    if not namespace:
        return None
    ns = namespace.strip()
    if not ns:
        return None
    return re.sub(r"[^0-9A-Za-z._-]+", "_", ns)
