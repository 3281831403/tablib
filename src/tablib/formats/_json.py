""" Tablib - JSON Support
"""

__lazy_modules__ = {"decimal", "json", "uuid", "tablib.utils"}

import decimal
import json
from uuid import UUID

import tablib

from ..utils import check_duplicate_headers


def serialize_objects_handler(obj):
    if isinstance(obj, (decimal.Decimal, UUID)):
        return str(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj


class JSONFormat:
    title = 'json'
    extensions = ('json', 'jsn')

    @classmethod
    def export_set(cls, dataset):
        """Returns JSON representation of Dataset."""
        check_duplicate_headers(dataset.headers)
        return json.dumps(
            dataset.dict, default=serialize_objects_handler, ensure_ascii=False
        )

    @classmethod
    def export_book(cls, databook):
        """Returns JSON representation of Databook."""
        for dataset in databook.sheets():
            check_duplicate_headers(dataset.headers)
        return json.dumps(
            databook._package(), default=serialize_objects_handler, ensure_ascii=False
        )

    @classmethod
    def import_set(cls, dset, in_stream):
        """Returns dataset from JSON stream."""

        # Parse first: a failing import must not wipe the current content.
        data = json.load(in_stream)
        if not data:
            dset.wipe()
        else:
            dset.dict = data

    @classmethod
    def import_book(cls, dbook, in_stream):
        """Returns databook from JSON stream."""

        # Build all sheets before wiping, so a failing import does not
        # destroy the current content.
        sheets = []
        for sheet in json.load(in_stream):
            data = tablib.Dataset()
            data.title = sheet['title']
            data.dict = sheet['data']
            sheets.append(data)
        dbook.wipe()
        for data in sheets:
            dbook.add_sheet(data)

    @classmethod
    def detect(cls, stream):
        """Returns True if given stream is valid JSON."""
        try:
            json.load(stream)
            return True
        except (TypeError, ValueError):
            return False
