"""Join separate label assignments and ID-prefixed sparse vectors."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from datamonger import _native
from datamonger._decode_libsvm import _csr
from datamonger._errors import UnsupportedDecoderError
from datamonger._models import (
    DatasetSplits,
    DecodedSplits,
    LogicalComponent,
    LogicalSparseMatrix,
    MultilabelSparseDataset,
)


def input_roles(options: Mapping[str, Any]) -> tuple[str, ...]:
    if set(options) != {"feature_count", "label_count", "train", "test"} or any(
        type(options[key]) is not int or not 1 <= options[key] < 2**53
        for key in ("feature_count", "label_count")
    ):
        raise UnsupportedDecoderError("invalid sparse label join options")
    roles = ["labels"]
    for split in ("train", "test"):
        shards = options[split]
        if (
            not isinstance(shards, list)
            or not shards
            or any(not isinstance(role, str) or not role for role in shards)
        ):
            raise UnsupportedDecoderError("each split requires ordered input roles")
        roles.extend(shards)
    if len(roles) != len(set(roles)):
        raise UnsupportedDecoderError("sparse label join roles must be distinct")
    return tuple(roles)


def validate_artifacts(artifacts: Sequence[Mapping[str, Any]]) -> None:
    if len({artifact["name"] for artifact in artifacts}) != len(artifacts) or any(
        artifact.get("format") != ("label-assignments" if index == 0 else "id-sparse")
        or artifact.get("compression") not in ("none", "gzip", "bzip2")
        for index, artifact in enumerate(artifacts)
    ):
        raise UnsupportedDecoderError("invalid sparse label join artifacts")


def decode_sparse_labels(
    paths: Sequence[Path], options: Mapping[str, Any], compressions: Sequence[str]
) -> DecodedSplits:
    components = tuple(
        _native.decode_sparse_label_join(
            list(zip(paths, compressions, strict=True)),
            len(options["train"]),
            options["feature_count"],
            options["label_count"],
        )
    )
    codes = components[-1]
    assert isinstance(codes, LogicalComponent)
    label_codes = tuple(str(value) for value in codes.values)
    splits = {}
    for name, start in (("train", 0), ("test", 3)):
        features, response, documents = components[start : start + 3]
        assert isinstance(features, LogicalSparseMatrix)
        assert isinstance(response, LogicalSparseMatrix)
        assert isinstance(documents, LogicalComponent)
        assert isinstance(documents.values, np.ndarray)
        splits[name] = MultilabelSparseDataset(
            _csr(features), _csr(response), 0, documents.values, label_codes
        )
    return DecodedSplits(DatasetSplits(splits), components)
