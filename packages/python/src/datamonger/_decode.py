"""Delimited-text version 1 decoding through datamonger-core."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import numpy.typing as npt
import pandas as pd

from datamonger import _native
from datamonger._decoder_options import delimited_options
from datamonger._models import DecodedTable, LogicalComponent, Pathish


def _make_dataframe(components: tuple[LogicalComponent, ...]) -> pd.DataFrame:
    series: dict[str, pd.Series[Any]] = {}
    for component in components:
        mask = ~component.valid
        data: Any
        if component.logical_type == "string":
            native: list[Any] = [
                value if valid else pd.NA
                for value, valid in zip(component.values, component.valid, strict=True)
            ]
            data = pd.array(native, dtype=cast(Any, "string"))
        else:
            # The masked-array constructors take the unboxed values directly;
            # copies keep the frame independent of the logical components.
            typed = cast("npt.NDArray[Any]", component.values)
            if component.logical_type == "float64":
                data = pd.arrays.FloatingArray(typed.copy(), mask.copy())
            elif component.logical_type == "int64":
                data = pd.arrays.IntegerArray(typed.copy(), mask.copy())
            else:
                data = pd.arrays.BooleanArray(typed.copy(), mask.copy())
        series[component.name] = pd.Series(data)
    return pd.DataFrame(series)


def decode_delimited_text(
    path: Pathish,
    options: Mapping[str, object],
    *,
    compression: str = "none",
) -> DecodedTable:
    """Decode a delimited-text version 1 representation."""

    columns, missing_values, delimiter = delimited_options(options)
    components = cast(
        tuple[LogicalComponent, ...],
        tuple(
            _native.decode_delimited(
                Path(path), columns, sorted(missing_values), delimiter, compression
            )
        ),
    )
    return DecodedTable(data=_make_dataframe(components), components=components)
