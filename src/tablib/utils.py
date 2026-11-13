__lazy_modules__ = {"io"}

from io import BytesIO, StringIO


def check_duplicate_headers(headers):
    """
    Raise a ValueError if any header appears more than once. Formats that
    serialize rows as key/value mappings (JSON, YAML, ...) cannot represent
    repeated column names, so they must fail loudly instead of silently
    dropping columns.
    """
    headers = list(headers or [])
    duplicates = []
    for index, header in enumerate(headers):
        if header in headers[:index] and header not in duplicates:
            duplicates.append(header)
    if duplicates:
        raise ValueError(
            "Duplicate header(s) {} cannot be represented in this format".format(
                ", ".join(repr(header) for header in duplicates)
            )
        )


def normalize_input(stream):
    """
    Accept either a str/bytes stream or a file-like object and always return a
    file-like object.
    """
    if isinstance(stream, str):
        return StringIO(stream, newline='')
    elif isinstance(stream, bytes):
        return BytesIO(stream)
    return stream
