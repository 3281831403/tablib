""" Tablib - YAML Support.
"""

__lazy_modules__ = {"datetime", "decimal", "uuid", "yaml", "tablib.utils"}

import datetime
import decimal
from uuid import UUID

import yaml

import tablib

from ..utils import check_duplicate_headers


class TablibSafeDumper(yaml.SafeDumper):
    """SafeDumper that serializes objects the same way the JSON format does:
    Decimal and UUID as plain strings, dates/times as ISO strings."""


def _represent_as_str(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))


def _represent_as_isoformat(dumper, data):
    # Force quoting: an unquoted ISO value (e.g. 2026-11-13) would be
    # implicitly resolved back to a date/timestamp instead of a string.
    return dumper.represent_scalar(
        'tag:yaml.org,2002:str', data.isoformat(), style="'"
    )


TablibSafeDumper.add_representer(decimal.Decimal, _represent_as_str)
TablibSafeDumper.add_representer(UUID, _represent_as_str)
TablibSafeDumper.add_representer(datetime.datetime, _represent_as_isoformat)
TablibSafeDumper.add_representer(datetime.date, _represent_as_isoformat)
TablibSafeDumper.add_representer(datetime.time, _represent_as_isoformat)


class YAMLFormat:
    title = 'yaml'
    extensions = ('yaml', 'yml')

    @classmethod
    def export_set(cls, dataset):
        """Returns YAML representation of Dataset."""
        check_duplicate_headers(dataset.headers)
        return yaml.dump(
            dataset._package(),
            Dumper=TablibSafeDumper,
            default_flow_style=None,
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def export_book(cls, databook):
        """Returns YAML representation of Databook."""
        for dataset in databook.sheets():
            check_duplicate_headers(dataset.headers)
        return yaml.dump(
            databook._package(),
            Dumper=TablibSafeDumper,
            default_flow_style=None,
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def import_set(cls, dset, in_stream):
        """Returns dataset from YAML stream."""

        # Parse first: a failing import must not wipe the current content.
        data = yaml.safe_load(in_stream)
        if not data:
            dset.wipe()
        else:
            dset.dict = data

    @classmethod
    def import_book(cls, dbook, in_stream):
        """Returns databook from YAML stream."""

        # Build all sheets before wiping, so a failing import does not
        # destroy the current content.
        sheets = []
        for sheet in yaml.safe_load(in_stream):
            data = tablib.Dataset()
            data.title = sheet['title']
            data.dict = sheet['data']
            sheets.append(data)
        dbook.wipe()
        for data in sheets:
            dbook.add_sheet(data)

    @classmethod
    def detect(cls, stream):
        """Returns True if given stream is valid YAML."""
        try:
            _yaml = yaml.safe_load(stream)
            if isinstance(_yaml, (list, tuple, dict)):
                return True
            else:
                return False
        except (yaml.parser.ParserError, yaml.reader.ReaderError,
                yaml.scanner.ScannerError):
            return False
