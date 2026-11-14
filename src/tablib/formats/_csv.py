""" Tablib - *SV Support.
"""

__lazy_modules__ = {"csv", "io", "tablib.utils"}

import csv
from io import StringIO

from ..utils import open_text_stream

BOM = '\ufeff'


def _strip_bom(lines):
    """Yield lines with a leading byte-order mark removed from the first one."""
    for index, line in enumerate(lines):
        if index == 0 and line.startswith(BOM):
            line = line[len(BOM):]
        yield line


class CSVFormat:
    title = 'csv'
    extensions = ('csv',)

    DEFAULT_DELIMITER = ','

    # Byte streams of this format can be decoded with a text encoding.
    supports_encoding = True

    @classmethod
    def export_stream_set(cls, dataset, **kwargs):
        """Returns CSV representation of Dataset as file-like."""
        stream = StringIO()

        kwargs.setdefault('delimiter', cls.DEFAULT_DELIMITER)

        _csv = csv.writer(stream, **kwargs)

        for row in dataset._package(dicts=False):
            _csv.writerow(row)

        stream.seek(0)
        return stream

    @classmethod
    def export_set(cls, dataset, **kwargs):
        """Returns CSV representation of Dataset."""
        stream = cls.export_stream_set(dataset, **kwargs)
        return stream.getvalue()

    @classmethod
    def import_set(cls, dset, in_stream, headers=True, skip_lines=0, encoding=None,
                   **kwargs):
        """Returns dataset from CSV stream.

        ``in_stream`` may be a string, bytes, or a text or binary file-like
        object. Bytes are decoded as UTF-8 (removing a leading BOM) unless
        another ``encoding`` is given.
        """

        dset.wipe()

        kwargs.setdefault('delimiter', cls.DEFAULT_DELIMITER)

        with open_text_stream(in_stream, encoding) as stream:
            rows = csv.reader(_strip_bom(stream), **kwargs)
            for i, row in enumerate(rows):
                if i < skip_lines:
                    continue
                if i == skip_lines and headers:
                    dset.headers = row
                elif row:
                    if i > 0 and len(row) < dset.width:
                        row += [''] * (dset.width - len(row))
                    dset.append(row)

    @classmethod
    def detect(cls, stream, delimiter=None, encoding=None):
        """Returns True if given stream is valid CSV.

        Bytes and binary streams are decoded as UTF-8 (removing a leading
        BOM) unless another ``encoding`` is given. Undecodable binary data
        is not CSV.
        """
        try:
            with open_text_stream(stream, encoding) as text_stream:
                sample = text_stream.read(2048)
        except Exception:
            return False

        if sample.startswith(BOM):
            sample = sample[len(BOM):]
        # NUL bytes indicate a binary format (DBF, XLS, XLSX, ODS...).
        if '\x00' in sample:
            return False

        try:
            csv.Sniffer().sniff(sample, delimiters=delimiter or cls.DEFAULT_DELIMITER)
            return True
        except Exception:
            return False
