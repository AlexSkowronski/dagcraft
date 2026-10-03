"""
Excel workbooks, including ones with several sheets.
"""

import io
from typing import Any, BinaryIO

import pandas as pd

from dagcraft.data import require_table
from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("excel")
class ExcelFormat(Format):
    """
    Excel workbooks, through openpyxl.

    Reading takes the first sheet unless ``args`` sets ``sheet_name``. A
    list of sheet names, or ``sheet_name: null`` for every sheet, reads the
    sheets into one table with a ``sheet`` column naming each row's sheet
    (``sheet_column`` renames it).

    Writing a single table puts it in one sheet (``sheet_name`` names it).
    A write step with several inputs puts each in its own sheet, named
    after the input.
    """

    extensions = (".xlsx", ".xlsm")
    modules = ("openpyxl",)
    extra = "excel"
    multiple_inputs = True

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        sheet_column = args.pop("sheet_column", "sheet")
        result = pd.read_excel(file, **args)

        if not isinstance(result, dict):
            return result

        frames = [
            frame.assign(**{sheet_column: sheet}) for sheet, frame in result.items()
        ]
        return pd.concat(frames, ignore_index=True)

    def write(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        file: BinaryIO,
        **args: Any,
    ) -> None:
        args.setdefault("index", False)

        # Several inputs arrive as a dict of tables; a dict without any is a
        # document from a single input, which can't be a sheet.
        if isinstance(data, dict) and any(
            isinstance(frame, pd.DataFrame) for frame in data.values()
        ):
            sheets = {
                sheet: require_table(frame, f"Excel sheet '{sheet}'")
                for sheet, frame in data.items()
            }
        else:
            sheets = {args.pop("sheet_name", "Sheet1"): require_table(data, "Excel")}

        # Build the workbook in memory: not every storage can seek while writing.
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet, **args)

        file.write(buffer.getvalue())
