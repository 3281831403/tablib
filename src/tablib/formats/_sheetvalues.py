"""Lossless cell value encoding shared by the spreadsheet formats.

Spreadsheet applications store numbers as IEEE-754 doubles and have no
native representation for timezone-aware datetimes or text containing
control characters.  To guarantee that a tablib export -> import
round-trip preserves both the value and the type of every cell, values
that have no exact native representation are encoded as tagged text
markers::

    @@TABLIB-i:1234567890123456789@@         big integers
    @@TABLIB-d:1234567.89@@                  decimal.Decimal
    @@TABLIB-dt:2026-11-14T10:30:45+08:00@@  timezone-aware datetimes
    @@TABLIB-s:line\\x00with\\x01controls@@  text with control characters

Values that cannot be represented at all (timezone-aware times, or
plain text colliding with the reserved marker prefix) raise
:class:`tablib.exceptions.UnrepresentableValue` at export time, naming
the offending column and sheet row, instead of being silently rewritten.
"""

__lazy_modules__ = {"datetime", "decimal", "re", "tablib.exceptions"}

import datetime as dt
import decimal
import re

from ..exceptions import UnrepresentableValue

#: Prefix reserved for tablib type markers.  Plain text starting with
#: this prefix cannot be exported unambiguously and is rejected.
MARKER_PREFIX = "@@TABLIB-"
MARKER_SUFFIX = "@@"

#: Largest integer magnitude an IEEE-754 double (and therefore a
#: spreadsheet number cell) represents exactly.
MAX_SAFE_INTEGER = 2**53 - 1

# Control characters that are illegal in XML 1.0 character data
# (horizontal tab, line feed and carriage return are legal).
_UNSAFE_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_ESCAPE_SEQUENCE_RE = re.compile(r"\\(?:\\|x[0-9a-fA-F]{2})")


def _location(header, col_idx, row_number):
    parts = []
    if header is not None:
        parts.append(f"column {header!r}")
    parts.append(f"column {col_idx + 1}")
    parts.append(f"sheet row {row_number}")
    return ", ".join(parts)


def _encode_text(value):
    payload = value.replace("\\", "\\\\")
    payload = _UNSAFE_TEXT_RE.sub(
        lambda match: f"\\x{ord(match.group()):02x}", payload
    )
    return f"{MARKER_PREFIX}s:{payload}{MARKER_SUFFIX}"


def _decode_text(payload):
    def unescape(match):
        sequence = match.group()
        if sequence == "\\\\":
            return "\\"
        return chr(int(sequence[2:], 16))

    return _ESCAPE_SEQUENCE_RE.sub(unescape, payload)


def encode_cell(value, header=None, col_idx=0, row_number=1):
    """Return a version of `value` that survives a spreadsheet round-trip.

    Values with an exact native representation (ordinary ints, floats,
    plain text, naive dates/times, booleans, None) are returned
    unchanged.  Values without one are returned as text markers.  Values
    that can be neither stored nor marked raise
    :class:`tablib.exceptions.UnrepresentableValue`.

    `header`, `col_idx` (0-based) and `row_number` (1-based sheet row)
    are only used to locate the cell in error messages.
    """
    if isinstance(value, str):
        if value.startswith(MARKER_PREFIX):
            raise UnrepresentableValue(
                f"Cannot export text {value!r} "
                f"({_location(header, col_idx, row_number)}): it starts with "
                f"{MARKER_PREFIX!r} which is reserved for tablib type markers."
            )
        if _UNSAFE_TEXT_RE.search(value):
            return _encode_text(value)
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            return value
        return f"{MARKER_PREFIX}i:{value}{MARKER_SUFFIX}"
    if isinstance(value, decimal.Decimal):
        return f"{MARKER_PREFIX}d:{value}{MARKER_SUFFIX}"
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            return f"{MARKER_PREFIX}dt:{value.isoformat()}{MARKER_SUFFIX}"
        return value
    if isinstance(value, dt.time) and value.tzinfo is not None:
        raise UnrepresentableValue(
            f"Cannot export timezone-aware time {value!r} "
            f"({_location(header, col_idx, row_number)}): spreadsheet formats "
            "have no representation for it. Convert it to a datetime or drop "
            "the tzinfo first."
        )
    return value


def decode_cell(value):
    """Restore a value encoded by :func:`encode_cell`.

    Anything that is not a well-formed tablib marker (including text
    from foreign files that merely starts with the reserved prefix) is
    returned unchanged.
    """
    if not isinstance(value, str) or not value.startswith(MARKER_PREFIX):
        return value
    body = value[len(MARKER_PREFIX):]
    if not body.endswith(MARKER_SUFFIX):
        return value
    tag, sep, payload = body[:-len(MARKER_SUFFIX)].partition(":")
    if not sep:
        return value
    try:
        if tag == "i":
            return int(payload)
        if tag == "d":
            return decimal.Decimal(payload)
        if tag == "dt":
            return dt.datetime.fromisoformat(payload)
        if tag == "s":
            return _decode_text(payload)
    except (ValueError, ArithmeticError):
        pass
    return value
