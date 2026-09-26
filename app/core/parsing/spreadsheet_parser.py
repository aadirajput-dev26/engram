"""
Spreadsheet parser: Excel (.xlsx) and CSV (.csv).

Each sheet in an XLSX file becomes a ParsedPage.
A CSV file is treated as a single ParsedPage.
Data is stored both as a DetectedTable and as a
markdown text representation for downstream chunking.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.parsing.pdf_parser import DetectedTable, ParsedDocument, ParsedPage

logger = get_logger(__name__)


def parse_spreadsheet(file_path: str, is_csv: bool = False) -> ParsedDocument:
    """
    Parse an Excel or CSV file.

    Each sheet (XLSX) or the file itself (CSV) is treated as one ParsedPage.
    Tables are extracted as DetectedTable objects and raw_text holds a
    markdown/pipe-delimited string representation of the data.

    Args:
        file_path: Absolute path to the .xlsx or .csv file.
        is_csv:    Set to True when file_path is a CSV file.

    Returns:
        ParsedDocument with per-sheet/file results.
    """
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "pandas is required for spreadsheet parsing. "
            "Install it with: pip install pandas openpyxl"
        )

    pages: list[ParsedPage] = []
    all_tables: list[DetectedTable] = []

    if is_csv:
        try:
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
            df = df.fillna("")
            page, table = _dataframe_to_page(df, sheet_name="Sheet1", page_number=1)
            pages.append(page)
            all_tables.append(table)
        except Exception as e:
            logger.error("Failed to parse CSV %s: %s", file_path, e)
            raise
    else:
        try:
            xl = pd.ExcelFile(file_path)
        except Exception as e:
            logger.error("Failed to open Excel file %s: %s", file_path, e)
            raise

        for page_number, sheet_name in enumerate(xl.sheet_names, start=1):
            try:
                df = xl.parse(sheet_name, dtype=str, keep_default_na=False)
                df = df.fillna("")
                page, table = _dataframe_to_page(df, sheet_name=sheet_name, page_number=page_number)
                pages.append(page)
                all_tables.append(table)
            except Exception as e:
                logger.warning("Failed to parse sheet '%s': %s", sheet_name, e)

    detected_type = "csv" if is_csv else "excel"
    logger.info(
        "Parsed %s: %d sheet(s), %d table(s) extracted",
        detected_type, len(pages), len(all_tables),
    )
    return ParsedDocument(
        page_count=len(pages),
        pages=pages,
        detected_type=detected_type,
        tables=all_tables,
    )


def _dataframe_to_page(df, sheet_name: str, page_number: int):
    """Convert a pandas DataFrame into a ParsedPage + DetectedTable pair."""
    import pandas as pd

    # Build raw_cells (all rows including header)
    header_row = [str(c) for c in df.columns.tolist()]
    raw_cells: list[list[str]] = [header_row]
    for _, row in df.iterrows():
        raw_cells.append([str(v) for v in row.tolist()])

    table = DetectedTable(
        page_number=page_number,
        row_count=len(raw_cells),
        col_count=len(header_row),
        header_row=header_row,
        raw_cells=raw_cells,
    )

    # Markdown-style text representation
    raw_text = _df_to_markdown(header_row, raw_cells[1:])

    page = ParsedPage(
        page_number=page_number,
        raw_text=f"Sheet: {sheet_name}\n\n{raw_text}",
        source_type="native",
        text_density=len(raw_text),
        tables=[table],
        blocks=[],
    )
    return page, table


def _df_to_markdown(header: list[str], rows: list[list[str]]) -> str:
    """Render a table as a GitHub-style markdown table string."""
    if not header:
        return ""

    # Column widths
    col_widths = [len(h) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            width = col_widths[i] if i < len(col_widths) else len(cell)
            parts.append(str(cell).ljust(width))
        return "| " + " | ".join(parts) + " |"

    separator = "| " + " | ".join("-" * w for w in col_widths) + " |"
    lines = [fmt_row(header), separator]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)
