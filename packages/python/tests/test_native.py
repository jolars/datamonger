"""Compare the native backend with the independent pre-migration Python code."""

from __future__ import annotations

import bz2
import csv
import gzip
import hashlib
import importlib.machinery
import io
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from conftest import CASES, CORPUS, LIBSVM_OPTIONS, OPTIONS
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from reference import _canonical as reference_canonical
from reference import _decode as reference_delimited
from reference import _decode_libsvm as reference_libsvm
from test_canonical import GOLDEN_CASES, component_from_case

from datamonger import _native
from datamonger._canonical import canonical_bytes, canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
from datamonger._models import (
    LogicalComponent,
    LogicalDenseMatrix,
    LogicalSparseMatrix,
    LogicalValueComponent,
    SparseDataset,
    SparseDatasetSplit,
)
from datamonger.errors import DecodeError, UnsupportedDecoderError

COMPRESSORS = {"none": lambda b: b, "gzip": gzip.compress, "bzip2": bz2.compress}


def assert_components_equal(
    native: tuple[LogicalValueComponent, ...],
    reference: tuple[LogicalValueComponent, ...],
) -> None:
    assert len(native) == len(reference)
    for actual, expected in zip(native, reference, strict=True):
        assert type(actual) is type(expected)
        assert actual.name == expected.name
        assert actual.logical_type == expected.logical_type
        if isinstance(actual, (LogicalDenseMatrix, LogicalSparseMatrix)):
            assert actual.rows == expected.rows
            assert actual.columns == expected.columns
        if isinstance(actual, LogicalSparseMatrix):
            np.testing.assert_array_equal(actual.row_offsets, expected.row_offsets)
            np.testing.assert_array_equal(
                actual.column_indices, expected.column_indices
            )
        else:
            np.testing.assert_array_equal(actual.valid, expected.valid)
        if actual.logical_type == "string":
            assert actual.values == expected.values
        else:
            # Compare binary64 words, including the sign of zero.
            assert actual.values.dtype == expected.values.dtype
            assert actual.values.tobytes() == expected.values.tobytes()
    expected_bytes = reference_canonical.canonical_bytes(reference)
    assert canonical_bytes(native) == expected_bytes
    assert canonical_bytes(reference) == expected_bytes
    assert reference_canonical.canonical_bytes(native) == expected_bytes
    assert canonical_sha256(native) == hashlib.sha256(expected_bytes).hexdigest()


def assert_data_equal(actual: Any, expected: Any) -> None:
    assert type(actual) is type(expected)
    if isinstance(actual, pd.DataFrame):
        pd.testing.assert_frame_equal(actual, expected)
    elif isinstance(actual, SparseDataset):
        assert actual.features.format == expected.features.format == "csr"
        assert actual.features.shape == expected.features.shape
        np.testing.assert_array_equal(
            actual.features.toarray(), expected.features.toarray()
        )
        assert actual.response.dtype == expected.response.dtype
        np.testing.assert_array_equal(actual.response, expected.response)
    else:
        assert isinstance(actual, SparseDatasetSplit)
        assert_data_equal(actual.train, expected.train)
        assert_data_equal(actual.test, expected.test)


def test_backend_is_a_compiled_extension() -> None:
    assert any(
        _native.__file__.endswith(suffix)
        for suffix in importlib.machinery.EXTENSION_SUFFIXES
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
@pytest.mark.parametrize("compression", COMPRESSORS)
def test_shared_corpus_agrees_with_independent_python(
    case: dict[str, Any], compression: str, tmp_path: Path
) -> None:
    inputs = case["input"]
    paths = (
        [CORPUS / p for p in inputs.values()]
        if isinstance(inputs, dict)
        else [CORPUS / inputs]
    )
    compressed = []
    for index, path in enumerate(paths):
        destination = tmp_path / str(index)
        destination.write_bytes(COMPRESSORS[compression](path.read_bytes()))
        compressed.append(destination)
    decoder = case["decoder"]
    if decoder == "delimited-text":
        native = decode_delimited_text(
            compressed[0], case["recipe"], compression=compression
        )
        reference = reference_delimited.decode_delimited_text(
            compressed[0], case["recipe"], compression=compression
        )
    elif decoder == "libsvm":
        native = decode_libsvm(compressed[0], case["recipe"], compression=compression)
        reference = reference_libsvm.decode_libsvm(
            compressed[0], case["recipe"], compression=compression
        )
    else:
        kwargs = {"train_compression": compression, "test_compression": compression}
        native = decode_libsvm_split(*compressed, case["recipe"], **kwargs)
        reference = reference_libsvm.decode_libsvm_split(
            *compressed, case["recipe"], **kwargs
        )
    assert_components_equal(native.components, reference.components)
    assert_data_equal(native.data, reference.data)
    assert canonical_sha256(native.components) == case["expected_sha256"]


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["id"])
def test_canonical_corpus_agrees_with_independent_python(case: dict[str, Any]) -> None:
    component = component_from_case(case)
    expected = bytes.fromhex(case["expected_hex"])
    assert canonical_bytes((component,)) == expected
    assert reference_canonical.canonical_bytes((component,)) == expected
    assert canonical_sha256((component,)) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize(
    "case",
    json.loads((CORPUS / "malformed.json").read_bytes())["cases"],
    ids=lambda c: c["id"],
)
@pytest.mark.parametrize("compression", COMPRESSORS)
def test_malformed_corpus_preserves_error_classes(
    case: dict[str, Any], compression: str, tmp_path: Path
) -> None:
    inputs = case["input"]
    paths = list(inputs.values()) if isinstance(inputs, dict) else [inputs]
    artifacts = []
    for index, path in enumerate(paths):
        artifact = tmp_path / str(index)
        artifact.write_bytes(COMPRESSORS[compression]((CORPUS / path).read_bytes()))
        artifacts.append(artifact)
    for delimited, libsvm, split in (
        (decode_delimited_text, decode_libsvm, decode_libsvm_split),
        (
            reference_delimited.decode_delimited_text,
            reference_libsvm.decode_libsvm,
            reference_libsvm.decode_libsvm_split,
        ),
    ):
        with pytest.raises(DecodeError):
            if case["decoder"] == "libsvm-split":
                split(
                    *artifacts,
                    case["recipe"],
                    train_compression=compression,
                    test_compression=compression,
                )
            else:
                decoder = delimited if case["decoder"] == "delimited-text" else libsvm
                decoder(artifacts[0], case["recipe"], compression=compression)


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
@pytest.mark.parametrize(
    "decoder,reference,options,body",
    [
        (
            decode_delimited_text,
            reference_delimited.decode_delimited_text,
            OPTIONS | {"columns": [{"name": "x", "type": "string"}]},
            b"x\na\nb\n",
        ),
        (
            decode_libsvm,
            reference_libsvm.decode_libsvm,
            LIBSVM_OPTIONS,
            b"+1 1:2\n-1 2:3\n",
        ),
    ],
)
def test_compression_members_and_corruption_agree(
    compression: str,
    decoder: Callable[..., Any],
    reference: Callable[..., Any],
    options: Mapping[str, object],
    body: bytes,
    tmp_path: Path,
) -> None:
    compress = COMPRESSORS[compression]
    first, second = body.split(b"\n", maxsplit=1)
    artifact = tmp_path / "artifact"
    artifact.write_bytes(compress(first + b"\n") + compress(second))
    assert_components_equal(
        decoder(artifact, options, compression=compression).components,
        reference(artifact, options, compression=compression).components,
    )
    payload = compress(body)
    for contents in (
        payload[:-1],
        payload[: len(payload) // 2],
        b"invalid",
        payload[:-4] + bytes(v ^ 255 for v in payload[-4:]),
    ):
        artifact.write_bytes(contents)
        for backend in (decoder, reference):
            with pytest.raises(DecodeError):
                backend(artifact, options, compression=compression)


@pytest.mark.parametrize(
    "decoder,options",
    [(decode_delimited_text, OPTIONS), (decode_libsvm, LIBSVM_OPTIONS)],
)
def test_native_io_and_recipe_errors_keep_semantic_classes(
    decoder: Callable[..., Any], options: Mapping[str, object], tmp_path: Path
) -> None:
    with pytest.raises(DecodeError):
        decoder(tmp_path / "absent", options)
    with pytest.raises(UnsupportedDecoderError):
        decoder(tmp_path / "absent", options, compression="zip")
    with pytest.raises(UnsupportedDecoderError):
        decoder(tmp_path / "absent", options | {"unknown": True})


@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(raw=st.binary(max_size=128))
def test_arbitrary_bytes_agree_with_independent_python(
    raw: bytes, tmp_path: Path
) -> None:
    path = tmp_path / "random"
    path.write_bytes(raw)
    for native, reference, options in (
        (decode_libsvm, reference_libsvm.decode_libsvm, LIBSVM_OPTIONS),
        (
            decode_delimited_text,
            reference_delimited.decode_delimited_text,
            OPTIONS | {"columns": [{"name": "x", "type": "string"}]},
        ),
    ):
        try:
            expected = reference(path, options)
        except DecodeError:
            with pytest.raises(DecodeError):
                native(path, options)
        else:
            actual = native(path, options)
            assert_components_equal(actual.components, expected.components)
            assert_data_equal(actual.data, expected.data)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    values=st.lists(
        st.one_of(
            st.none(), st.floats(allow_infinity=False, allow_nan=False, width=64)
        ),
        max_size=32,
    )
)
def test_binary64_decoding_and_canonical_rounding_agree(
    values: list[float | None], tmp_path: Path
) -> None:
    path = tmp_path / "floats"
    path.write_text(
        "x\n" + "".join("NA\n" if v is None else f"{v!r}\n" for v in values),
        encoding="utf-8",
    )
    options = OPTIONS | {
        "columns": [{"name": "x", "type": "float64"}],
        "missing_values": ["NA"],
    }
    assert_components_equal(
        decode_delimited_text(path, options).components,
        reference_delimited.decode_delimited_text(path, options).components,
    )


@pytest.mark.parametrize(
    "logical_type,values",
    [
        ("float64", np.array([-0.0, np.nan, 2.0, 1e-320])),
        ("int64", np.array([-(2**63), 0, 1, 2**63 - 1], dtype=np.int64)),
        ("bool", np.array([True, False, True, True])),
        ("string", ("e\u0301", "é", "\x00", "\ud800")),
    ],
)
def test_canonical_dense_vectors_and_sliced_storage_agree(
    logical_type: str, values: Any
) -> None:
    valid = np.array([True, True, True, False])
    for component in (
        LogicalComponent("x", logical_type, values, valid),
        LogicalDenseMatrix("x", logical_type, 2, 2, values, valid),
        LogicalComponent("x", logical_type, values[::2], valid[::2]),
    ):
        assert canonical_bytes((component,)) == reference_canonical.canonical_bytes(
            (component,)
        )
        assert canonical_sha256((component,)) == reference_canonical.canonical_sha256(
            (component,)
        )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    values=st.lists(
        st.text(
            alphabet=st.characters(
                exclude_categories=("Cs",), exclude_characters="\r\n"
            ),
            max_size=32,
        ),
        max_size=16,
    )
)
def test_unicode_and_csv_quoting_agree(values: list[str], tmp_path: Path) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["x"])
    writer.writerows([value] for value in values)
    path = tmp_path / "strings"
    path.write_bytes(buffer.getvalue().encode("utf-8"))
    options = OPTIONS | {
        "columns": [{"name": "x", "type": "string"}],
        "missing_values": [],
    }
    assert_components_equal(
        decode_delimited_text(path, options).components,
        reference_delimited.decode_delimited_text(path, options).components,
    )


@pytest.mark.skipif(os.name == "nt", reason="uses POSIX signals")
def test_native_decode_releases_gil_and_preserves_signal_exception(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "large.libsvm"
    artifact.write_bytes(b"+1 1:2 2:3 4:5\n" * 500_000)
    script = """
import os
from pathlib import Path
import signal
import sys
import threading
import time
from datamonger._decode_libsvm import decode_libsvm

class Canceled(Exception):
    pass

def interrupt(signum, frame):
    raise Canceled("canceled from Python")

def send_signal():
    time.sleep(0.01)
    os.kill(os.getpid(), signal.SIGUSR1)

options = {
    "index_base": 1, "feature_count": 4, "duplicate_features": "error",
    "label_type": "int64", "row_order": "source", "target_name": "response",
}
signal.signal(signal.SIGUSR1, interrupt)
worker = threading.Thread(target=send_signal)
worker.start()
try:
    decode_libsvm(Path(sys.argv[1]), options)
except Canceled as error:
    assert str(error) == "canceled from Python"
else:
    raise AssertionError("decoding finished without releasing the GIL to the sender")
finally:
    worker.join()
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)

# Cancellation must release the reader and leave the extension usable.
path = Path(sys.argv[1])
path.write_bytes(b"+1 1:2\\n")
assert decode_libsvm(path, options).data.response.tolist() == [1]
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(artifact)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
# Pytest exports case names in an environment variable, which Windows limits.
@pytest.mark.parametrize(
    "suffix",
    [b"", b"\0", b"\0" * 8193, b"junk", b"B", b"BZ", b"BZh9"],
    ids=["empty", "zero", "zero-padding", "junk", "b", "bz", "bzip2-header"],
)
def test_compressed_trailing_bytes_preserve_python_behavior(
    compression: str, suffix: bytes, tmp_path: Path
) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_bytes(COMPRESSORS[compression](b"+1 1:2\n") + suffix)
    try:
        expected = reference_libsvm.decode_libsvm(
            artifact, LIBSVM_OPTIONS, compression=compression
        )
    except DecodeError:
        with pytest.raises(DecodeError):
            decode_libsvm(artifact, LIBSVM_OPTIONS, compression=compression)
    else:
        assert_components_equal(
            decode_libsvm(artifact, LIBSVM_OPTIONS, compression=compression).components,
            expected.components,
        )


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
def test_empty_compressed_artifacts_preserve_python_behavior(
    compression: str, tmp_path: Path
) -> None:
    artifact = tmp_path / "empty"
    artifact.write_bytes(b"")
    if compression == "bzip2":
        for decoder in (decode_libsvm, reference_libsvm.decode_libsvm):
            with pytest.raises(DecodeError):
                decoder(artifact, LIBSVM_OPTIONS, compression=compression)
    else:
        assert_components_equal(
            decode_libsvm(artifact, LIBSVM_OPTIONS, compression=compression).components,
            reference_libsvm.decode_libsvm(
                artifact, LIBSVM_OPTIONS, compression=compression
            ).components,
        )


def test_gzip_padding_between_members_preserves_python_behavior(tmp_path: Path) -> None:
    artifact = tmp_path / "padded"
    artifact.write_bytes(
        gzip.compress(b"+1 1:2\n") + b"\0" * 8193 + gzip.compress(b"-1 2:3\n")
    )
    assert_components_equal(
        decode_libsvm(artifact, LIBSVM_OPTIONS, compression="gzip").components,
        reference_libsvm.decode_libsvm(
            artifact, LIBSVM_OPTIONS, compression="gzip"
        ).components,
    )


@pytest.mark.parametrize("compression", ["gzip", "bzip2"])
def test_compressed_buffers_preserve_all_records(
    compression: str, tmp_path: Path
) -> None:
    body = "".join(f"{index} 1:{index + 1}\n" for index in range(20_000)).encode()
    artifact = tmp_path / "large-compressed"
    artifact.write_bytes(COMPRESSORS[compression](body))
    assert_components_equal(
        decode_libsvm(artifact, LIBSVM_OPTIONS, compression=compression).components,
        reference_libsvm.decode_libsvm(
            artifact, LIBSVM_OPTIONS, compression=compression
        ).components,
    )
