"""Small helpers that render COBOL statements for test bodies."""


def lit(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def set_text(field: str, value: str, length_field: str | None = None) -> str:
    """MOVE a literal into ``field`` and optionally its length into another."""
    if len(value) <= 30:
        lines = [f"MOVE {lit(value)} TO {field}"]
    else:
        lines = [f"MOVE SPACES TO {field}"]
        for pos in range(0, len(value), 30):
            chunk = value[pos:pos + 30]
            lines.append(f"MOVE {lit(chunk)}")
            lines.append(f"  TO {field}({pos + 1}:{len(chunk)})")
    if length_field:
        lines.append(f"MOVE {len(value)} TO {length_field}")
    return "\n".join(lines)


def query_string(value: str) -> str:
    return set_text("WEB-QUERYSTRING", value, "WEB-QUERYSTRING-LENGTH")


def web_path(value: str) -> str:
    return set_text("WEB-PATH", value, "WEB-PATH-LENGTH")


def method(name: str) -> str:
    return f"MOVE WEB-HTTP-{name} TO WEB-HTTPMETHOD"
