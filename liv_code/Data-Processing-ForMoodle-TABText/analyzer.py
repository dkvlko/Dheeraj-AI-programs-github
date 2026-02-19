from typing import List
import metadata

def validate_uniformity(data):

    if not data:
        return True

    expected_cols = len(data[0])

    for i, row in enumerate(data, start=1):
        if len(row) != expected_cols:
            raise ValueError(
                f"Row {i} has {len(row)} columns, "
                f"expected {expected_cols}"
            )

    return True


def analyze_uniform_tabular_data(
    data: List[List[str]]
) -> tuple[int, int]:
    """
    Analyze TAB CSV where all rows have equal columns.

    Returns:
        (row_count, column_count)
    Also stores values globally in metadata.
    """

    # ---- Row count ----
    row_count = len(data)

    # ---- Column count ----
    if row_count == 0:
        column_count = 0
    else:
        column_count = len(data[0])

    # ---- Store globally ----
    metadata.TOTAL_ROWS = row_count
    metadata.TOTAL_COLUMNS = column_count

    return row_count, column_count
