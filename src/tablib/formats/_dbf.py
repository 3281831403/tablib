""" Tablib - DBF Support.
"""

__lazy_modules__ = {
    "io",
    "os",
    "sys",
    "tablib._vendor",
    "tablib.exceptions",
    "tempfile",
}

import datetime
import io
import os
import sys
import tempfile

from .._vendor.dbfpy import dbf, dbfnew
from .._vendor.dbfpy import record as dbfrecord
from ..exceptions import HeadersNeeded


class DBFFormat:
    title = 'dbf'
    extensions = ('dbf',)

    DEFAULT_ENCODING = 'utf-8'

    # width (and decimals) of the numeric fields, matching the historical
    # output so existing byte-for-byte consumers keep working
    NUMERIC_WIDTH = 10
    NUMERIC_DECIMALS = 8
    CHARACTER_WIDTH = 80

    @staticmethod
    def _column_label(index, header):
        """Human-readable identifier used in error messages."""
        return f'column {index + 1} ({header!r})'

    @classmethod
    def _validate_headers(cls, headers):
        """Validate field names against the DBF rules.

        Field names are limited to 10 characters and must be unique
        in a case-insensitive way (DBF stores names in upper case).
        """
        seen = set()
        for index, header in enumerate(headers):
            name = str(header)
            label = cls._column_label(index, header)
            if '\0' in name:
                raise ValueError(
                    f'{label}: DBF field names must not contain NUL characters'
                )
            if len(name) > 10:
                raise ValueError(
                    f'{label}: DBF field names must be at most 10 characters long, '
                    f'got {len(name)}: {name!r}'
                )
            upper_name = name.upper()
            if upper_name in seen:
                raise ValueError(
                    f'{label}: duplicate DBF field name {upper_name!r}; '
                    'field names are case-insensitive and must be unique'
                )
            seen.add(upper_name)

    @staticmethod
    def _value_kind(value):
        """Map a Python value to a DBF-compatible column kind.

        Returns ``None`` for empty values, which do not constrain the
        column type. ``bool`` is checked before ``int`` because it is a
        subclass of ``int``.
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return 'L'
        if isinstance(value, (int, float)):
            return 'N'
        if isinstance(value, datetime.datetime):
            # DBF date fields keep the calendar date; time-of-day is dropped
            return 'D'
        if isinstance(value, datetime.date):
            return 'D'
        if isinstance(value, str):
            return 'C'
        return 'UNSUPPORTED'

    @classmethod
    def _infer_field_types(cls, dataset):
        """Determine one DBF field type per column from all rows.

        The type is derived from every non-empty value in a column
        rather than just the first row. Columns mixing incompatible
        types, or containing unsupported values, raise ``ValueError``
        naming the offending column.
        """
        field_types = []
        headers = dataset.headers
        for index, header in enumerate(headers):
            kinds = set()
            unsupported = None
            for row in dataset:
                kind = cls._value_kind(row[index])
                if kind == 'UNSUPPORTED':
                    unsupported = row[index]
                    break
                if kind is not None:
                    kinds.add(kind)
            label = cls._column_label(index, header)
            if unsupported is not None:
                raise ValueError(
                    f'{label}: value of type {type(unsupported).__name__} '
                    'cannot be stored in a DBF field'
                )
            if not kinds:
                # empty table or fully blank column: fall back to text
                field_types.append('C')
            elif len(kinds) == 1:
                field_types.append(kinds.pop())
            else:
                raise ValueError(
                    f'{label}: mixed column types {sorted(kinds)}; '
                    'a DBF field has a single type for every row'
                )
        return field_types

    @classmethod
    def _check_character_widths(cls, dataset, field_types):
        """Reject character values that would be silently truncated."""
        encoding = sys.getfilesystemencoding()
        for index, (header, field_type) in enumerate(
            zip(dataset.headers, field_types)
        ):
            if field_type != 'C':
                continue
            label = cls._column_label(index, header)
            for row in dataset:
                value = row[index]
                if value is None:
                    continue
                width = len(str(value).encode(encoding))
                if width > cls.CHARACTER_WIDTH:
                    raise ValueError(
                        f'{label}: character value is {width} bytes long but a '
                        f'DBF character field holds at most {cls.CHARACTER_WIDTH}; '
                        'shorten the value or it would be silently truncated'
                    )

    @classmethod
    def export_set(cls, dataset):
        """Returns DBF representation of a Dataset"""
        if dataset.headers is None:
            raise HeadersNeeded(
                'DBF export requires headers: every field needs a column name'
            )
        headers = [str(header) for header in dataset.headers]
        cls._validate_headers(headers)
        field_types = cls._infer_field_types(dataset)
        cls._check_character_widths(dataset, field_types)

        new_dbf = dbfnew.dbf_new()
        for fieldname, field_type in zip(headers, field_types):
            if field_type == 'N':
                new_dbf.add_field(
                    fieldname, 'N', cls.NUMERIC_WIDTH, cls.NUMERIC_DECIMALS
                )
            elif field_type == 'L':
                new_dbf.add_field(fieldname, 'L')
            elif field_type == 'D':
                new_dbf.add_field(fieldname, 'D')
            else:
                new_dbf.add_field(fieldname, 'C', cls.CHARACTER_WIDTH)

        temp_file, temp_uri = tempfile.mkstemp()
        try:
            new_dbf.write(temp_uri)

            dbf_file = dbf.Dbf(temp_uri, readOnly=0)
            try:
                for row in dataset:
                    record = dbfrecord.DbfRecord(dbf_file)
                    for fieldname, field_value in zip(headers, row):
                        record[fieldname] = field_value
                    record.store()
                # an empty table still needs the end-of-file marker
                if not dataset:
                    dbf_file.stream.write(b"\x1A")
            finally:
                dbf_file.close()

            with open(temp_uri, 'rb') as dbf_stream:
                stream = io.BytesIO(dbf_stream.read())
        finally:
            os.close(temp_file)
            os.remove(temp_uri)
        return stream.getvalue()

    @classmethod
    def import_set(cls, dset, in_stream):
        """Returns a dataset from a DBF stream."""

        dset.wipe()
        _dbf = dbf.Dbf(in_stream)
        dset.headers = _dbf.fieldNames
        for record in range(_dbf.recordCount):
            row = [_dbf[record][f] for f in _dbf.fieldNames]
            dset.append(row)

    @classmethod
    def detect(cls, stream):
        """Returns True if the given stream is valid DBF"""
        try:
            dbf.Dbf(stream, readOnly=True)
            return True
        except Exception:
            return False
