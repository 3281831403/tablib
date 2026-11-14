__lazy_modules__ = {"contextlib", "io"}

from contextlib import contextmanager
from io import BytesIO, StringIO, TextIOWrapper, UnsupportedOperation

# `utf-8-sig` is regular UTF-8 plus BOM removal, which is what spreadsheet
# applications write for their "CSV UTF-8" exports.
DEFAULT_ENCODING = 'utf-8-sig'


def decode_bytes(data, encoding=None):
    """Decode raw bytes to text, removing a leading BOM by default."""
    return bytes(data).decode(encoding or DEFAULT_ENCODING)


def is_binary_stream(stream):
    """Return True if the stream yields bytes instead of strings."""
    if isinstance(stream, (bytes, bytearray)):
        return True
    if isinstance(stream, str):
        return False
    # Text streams (`open(..., 'r')`, TextIOWrapper) expose their encoding.
    if getattr(stream, 'encoding', None) is not None:
        return False
    try:
        probe = stream.read(0)
    except (AttributeError, TypeError, ValueError, UnsupportedOperation):
        return False
    return isinstance(probe, (bytes, bytearray))


@contextmanager
def open_text_stream(stream, encoding=None):
    """
    Yield a text stream suitable for readers such as `csv.reader`.

    Raw strings are wrapped in a StringIO, bytes are decoded (`utf-8-sig` by
    default, which also strips a leading BOM) and binary file-like objects are
    wrapped in a TextIOWrapper. The caller's stream is never closed.
    """
    if isinstance(stream, str):
        yield StringIO(stream, newline='')
        return
    if isinstance(stream, (bytes, bytearray)):
        yield StringIO(decode_bytes(stream, encoding), newline='')
        return
    if not is_binary_stream(stream):
        yield stream
        return

    try:
        wrapper = TextIOWrapper(stream, encoding=encoding or DEFAULT_ENCODING, newline='')
    except (AttributeError, TypeError, ValueError):
        # Not a buffered binary stream (e.g. a custom storage wrapper):
        # fall back to reading it completely.
        yield StringIO(decode_bytes(stream.read(), encoding), newline='')
        return

    try:
        yield wrapper
    finally:
        # Detach instead of close: the stream belongs to the caller and may
        # still be used (or explicitly closed) afterwards.
        try:
            wrapper.detach()
        except ValueError:
            pass


def no_format_message(stream):
    """
    Return an explanatory message when no format could be detected for
    ``stream``, or an empty string when a generic error is appropriate.
    """
    try:
        probe = _peek(stream)
    except (AttributeError, TypeError, ValueError, UnsupportedOperation):
        return ''
    if not isinstance(probe, (bytes, bytearray)):
        return ''

    try:
        bytes(probe).decode(DEFAULT_ENCODING)
    except UnicodeDecodeError:
        return (
            'Could not detect the format of the given data. It is not valid '
            'UTF-8: if it is a text file in another encoding, pass that '
            "encoding explicitly, e.g. Dataset().load(stream, 'csv', "
            "encoding='gbk'); if it is a binary file, pass its format name "
            "explicitly, e.g. Dataset().load(stream, 'xlsx')."
        )
    return ''


def _peek(stream, size=2048):
    """Return the first ``size`` units of ``stream``, restoring its position."""
    position = stream.tell() if hasattr(stream, 'tell') else None
    try:
        return stream.read(size)
    finally:
        if position is not None and hasattr(stream, 'seek'):
            stream.seek(position)


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
