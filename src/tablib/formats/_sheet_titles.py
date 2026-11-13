""" Tablib - shared worksheet naming rules for workbook formats.

The workbook formats (XLS, XLSX and ODS) all represent the sheets of a
:class:`~tablib.core.Databook` as named worksheets and require unique
worksheet names. Excel additionally forbids a set of characters and
limits names to 31 characters; those names are normalized before the
uniqueness check, so two original titles that collapse to the same
normalized name are also rejected.
"""

__lazy_modules__ = {"re"}

import re

from ..exceptions import DuplicateSheetName, EmptyDatabook

INVALID_TITLE_REGEX = re.compile(r'[\\*?:/\[\]]')

#: Maximum worksheet name length supported by Excel (XLS/XLSX).
MAX_SHEET_TITLE_LENGTH = 31


def safe_excel_sheet_title(title, replace="-"):
    """Normalize ``title`` the way Excel (XLS/XLSX) requires.

    Characters which are not permitted in an Excel worksheet name are
    replaced with ``replace`` and the result is truncated to 31 chars.
    """
    return re.sub(INVALID_TITLE_REGEX, replace, title)[:MAX_SHEET_TITLE_LENGTH]


def resolve_sheet_title(dataset, index, *, normalize=None):
    """Return the worksheet name used for a sheet of a Databook.

    Datasets without a title fall back to the ``Sheet{index}`` naming
    shared by every workbook format. ``normalize`` is applied to real
    titles; pass ``None`` for formats (ODS) that store titles verbatim.
    """
    if dataset.title:
        if normalize is not None:
            return normalize(dataset.title)
        return dataset.title
    return f"Sheet{index}"


def validate_book_sheet_titles(databook, *, normalize=None):
    """Validate the worksheet names of every sheet in ``databook``.

    ``normalize`` maps a dataset title to the worksheet name the target
    format will actually store (``None`` means the title is stored
    verbatim). A :class:`~tablib.exceptions.EmptyDatabook` is raised when
    the databook has no sheets and :class:`~tablib.exceptions.DuplicateSheetName`
    when two sheets resolve to the same worksheet name. The original
    dataset titles are included in the error message.
    """
    datasets = databook._datasets
    if not datasets:
        raise EmptyDatabook(
            "Cannot export an empty Databook: add at least one sheet "
            "before exporting."
        )

    used = {}
    for index, dataset in enumerate(datasets):
        sheet_title = resolve_sheet_title(dataset, index, normalize=normalize)
        if sheet_title in used:
            first_title, first_index = used[sheet_title]
            raise DuplicateSheetName(
                f"Duplicate worksheet name {sheet_title!r}: sheets "
                f"{first_index} ({first_title!r}) and {index} "
                f"({dataset.title!r}) resolve to the same name."
            )
        used[sheet_title] = (dataset.title, index)
