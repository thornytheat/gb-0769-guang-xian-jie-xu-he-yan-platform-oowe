import csv
from io import StringIO

from app.errors import InspectionError

SLACK_HEADER = ('coil_id', 'route_m', 'length_m', 'kind')
KINDS = frozenset({'COIL', 'CLEAR'})


def read_slack_rows(text):
    """Yield (line, raw, values, reason) for a slack registry CSV."""
    text = text.removeprefix('﻿')
    if not text:
        raise InspectionError('EMPTY_FILE', 'slack')
    reader = csv.reader(StringIO(text, newline=''), strict=True)
    header = None
    try:
        while True:
            line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                if header is None:
                    raise InspectionError('BLANK_FILE', 'slack')
                return
            if not any(value.strip() for value in row):
                if header is not None:
                    yield line, row, None, 'BLANK'
                continue
            if header is None:
                header = [value.strip() for value in row]
                if sorted(header) != sorted(SLACK_HEADER):
                    raise InspectionError('BAD_HEADER', 'slack')
                continue
            if row == header:
                yield line, row, None, 'REPEATED_HEADER'
            elif len(row) != len(header):
                yield line, row, None, 'COLUMN_COUNT'
            else:
                yield line, row, dict(zip(header, row)), None
    except csv.Error:
        raise InspectionError('CSV_SYNTAX', 'slack') from None
