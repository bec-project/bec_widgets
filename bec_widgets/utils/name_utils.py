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
