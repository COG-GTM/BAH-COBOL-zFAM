"""Small helpers that render COBOL statements for test bodies."""


def lit(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def set_text(field: str, value: str, length_field: str | None = None) -> str:
    """MOVE a literal into ``field`` and optionally its length into another."""
    lines = [f"MOVE {lit(value)} TO {field}"]
    if length_field:
        lines.append(f"MOVE {len(value)} TO {length_field}")
    return "\n".join(lines)


def query_string(value: str) -> str:
    return set_text("WEB-QUERYSTRING", value, "WEB-QUERYSTRING-LENGTH")


def web_path(value: str) -> str:
    return set_text("WEB-PATH", value, "WEB-PATH-LENGTH")


def method(name: str) -> str:
    return f"MOVE WEB-HTTP-{name} TO WEB-HTTPMETHOD"
