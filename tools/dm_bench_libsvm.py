"""Prepare registry inputs and benchmark LIBSVM readers or warm-cache fetches."""

from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import platform
import resource
import shutil
import subprocess
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from statistics import median
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

CASES = {"a9a": "train", "cadata": "data", "rcv1-binary": "train"}
READERS = {
    "datamonger": "datamonger",
    "sklearn": "scikit-learn",
    "libsvm": "libsvm-official",
}
T = TypeVar("T")


def prepare(args: argparse.Namespace) -> None:
    """Stage one uncompressed artifact per case and optionally seed fetch splits."""
    from datamonger import BUNDLED_REGISTRY, data_info, fetch_artifact

    directory = args.directory
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name in args.dataset or CASES:
        role = CASES[name]
        reference = f"libsvm:{name}@1"
        settings = {
            "registry": BUNDLED_REGISTRY,
            "cache_dir": directory / "cache",
            "offline": args.offline,
        }
        info = data_info(reference, **settings)
        selected = info.representation["inputs"][role]
        for artifact in info.artifacts:
            if artifact["name"] != selected and not args.seed_fetch:
                continue
            source = fetch_artifact(reference, artifact=artifact["name"], **settings)
            if artifact["name"] != selected:
                continue
            compression = artifact["compression"]
            if compression not in {"bzip2", "none"}:
                raise ValueError(f"unsupported benchmark compression: {compression}")
            open_source = bz2.open if compression == "bzip2" else open
            with NamedTemporaryFile(dir=directory, delete=False) as output:
                temporary = Path(output.name)
            try:
                with (
                    open_source(source, "rb") as stream,
                    temporary.open("wb") as output,
                ):
                    shutil.copyfileobj(stream, output)
                path = directory / f"{name}.libsvm"
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            options = info.representation["options"]
            print(f"{path} {options['feature_count']} {options['label_type']}")


def measure(load: Callable[[], T], repeats: int) -> tuple[T, dict[str, Any]]:
    """Warm up and time individual loads with at most one result alive."""
    load()
    samples = []
    for index in range(repeats):
        start = perf_counter()
        result = load()
        samples.append(perf_counter() - start)
        if index + 1 < repeats:
            del result
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return result, {
        "median_ms": 1000 * median(samples),
        "samples_ms": [1000 * sample for sample in samples],
        "peak_rss_mib": rss / (2**20 if sys.platform == "darwin" else 2**10),
    }


def compare_output(matrix: csr_matrix, labels: Any, label_type: str) -> str:
    """Fingerprint normalized CSR arrays, ignoring explicit zero entries."""
    import numpy as np

    matrix.eliminate_zeros()
    matrix.sort_indices()
    labels = np.asarray(labels)
    label_dtype = "<f8"
    if label_type == "int64":
        if labels.dtype.kind == "f" and not (
            np.all(labels >= -(2**63))
            and np.all(labels < 2**63)
            and np.all(labels == np.trunc(labels))
        ):
            raise ValueError("reader returned labels outside the int64 domain")
        label_dtype = "<i8"
    digest = hashlib.sha256()
    for array, dtype in (
        (matrix.shape, "<i8"),
        (matrix.indptr, "<i8"),
        (matrix.indices, "<i8"),
        (matrix.data, "<f8"),
        (labels, label_dtype),
    ):
        values = np.asarray(array, dtype=dtype)
        digest.update(memoryview(values).cast("B"))
    return digest.hexdigest()


def reader_result(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np

    features = args.features
    path = str(args.path)

    if args.reader == "datamonger":
        from datamonger._decode_libsvm import decode_libsvm

        def datamonger_load() -> tuple[csr_matrix, Any]:
            options = {
                "feature_count": features,
                "label_type": args.label_type,
                "target_name": "response",
                "index_base": 1,
                "duplicate_features": "error",
                "row_order": "source",
            }
            data = decode_libsvm(
                path, options, decoder_version=args.decoder_version
            ).data
            return data.features, data.response

        load = datamonger_load
    elif args.reader == "sklearn":
        from sklearn.datasets import load_svmlight_file

        def sklearn_load() -> tuple[csr_matrix, Any]:
            return load_svmlight_file(
                path, n_features=features, zero_based=False, dtype=np.float64
            )

        load = sklearn_load
    else:
        from libsvm.svmutil import svm_read_problem

        def libsvm_load() -> tuple[csr_matrix, Any]:
            labels, matrix = svm_read_problem(path, return_scipy=True)
            if matrix.shape[1] < features:
                matrix.resize((matrix.shape[0], features))
            return matrix, labels

        load = libsvm_load

    (matrix, labels), stats = measure(load, args.repeats)
    stats.update(
        reader=args.reader,
        version=version(READERS[args.reader]),
        mib_per_s=args.path.stat().st_size / (2**20 * stats["median_ms"] / 1000),
        shape=matrix.shape,
        stored_entries=matrix.nnz,
        index_dtype=str(matrix.indices.dtype),
        offset_dtype=str(matrix.indptr.dtype),
        label_dtype=str(np.asarray(labels).dtype),
        output_sha256=compare_output(matrix, labels, args.label_type),
    )
    return stats


def reader_comparison(args: argparse.Namespace) -> None:
    with args.path.open("rb") as stream:
        input_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    results = []
    for reader in READERS:
        command = [
            sys.executable,
            __file__,
            "read",
            str(args.path),
            str(args.features),
            args.label_type,
            "--decoder-version",
            str(args.decoder_version),
            "--repeats",
            str(args.repeats),
            "--reader",
            reader,
        ]
        results.append(json.loads(subprocess.check_output(command, text=True)))
    print(
        json.dumps(
            {
                "path": str(args.path),
                "input_sha256": input_digest,
                "datamonger_decoder_version": args.decoder_version,
                "python": platform.python_version(),
                "numpy": version("numpy"),
                "scipy": version("scipy"),
                "platform": platform.platform(),
                "results": results,
            },
            indent=2,
        )
    )
    if len({result["output_sha256"] for result in results}) != 1:
        raise SystemExit("Readers returned different matrix values, shapes, or labels")


def fetch_comparison(args: argparse.Namespace) -> None:
    from datamonger import BUNDLED_REGISTRY, fetch_data

    comparisons = []
    for verify in (False, True):
        results = {}
        for name in args.dataset or CASES:
            reference = f"libsvm:{name}@1"

            def load(reference: str = reference, verify: bool = verify) -> Any:
                return fetch_data(
                    reference,
                    registry=BUNDLED_REGISTRY,
                    cache_dir=args.directory / "cache",
                    offline=True,
                    verify_decoded=verify,
                )

            result, stats = measure(load, args.repeats)
            del result
            # RSS is cumulative in this process and cannot be attributed to a case.
            del stats["peak_rss_mib"]
            results[reference] = stats
        comparisons.append({"verify_decoded": verify, "results": results})
    print(
        json.dumps(
            {"registry": BUNDLED_REGISTRY.release, "comparisons": comparisons}, indent=2
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("prepare", help="stage uncompressed registry inputs")
    stage.add_argument("directory", type=Path)
    stage.add_argument("--offline", action="store_true")
    stage.add_argument(
        "--seed-fetch", action="store_true", help="also cache other splits"
    )
    read = commands.add_parser("read", help="compare readers on one uncompressed file")
    read.add_argument("path", type=Path)
    read.add_argument("features", type=int)
    read.add_argument("label_type", choices=("int64", "float64"))
    read.add_argument("--decoder-version", type=int, choices=(1, 2), default=1)
    read.add_argument("--reader", choices=READERS, help=argparse.SUPPRESS)
    fetch = commands.add_parser("fetch", help="measure offline, warm-cache fetches")
    fetch.add_argument("directory", type=Path)
    for command in (stage, fetch):
        command.add_argument("--dataset", choices=CASES, action="append")
    for command in (read, fetch):
        command.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if getattr(args, "repeats", 1) <= 0:
        parser.error("--repeats must be positive")
    if args.command == "prepare":
        prepare(args)
    elif args.command == "fetch":
        fetch_comparison(args)
    elif args.reader is None:
        reader_comparison(args)
    else:
        print(json.dumps(reader_result(args)))


if __name__ == "__main__":
    main()
