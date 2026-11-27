"""Join the LYRL2004 vectors and topic assignments by Reuters document ID."""

import argparse
import gzip
import hashlib
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

# Figshare file IDs, compressed sizes, and SHA-256 digests.
SOURCES = {
    "5976048": (
        7272130,
        "2a98e5e5d8b770bded93afc8930d88299474317fe14181aee1466cc754d0d1c1",
    ),
    "5976057": (
        18594396,
        "5468f656d0ba7a83afc7ad44841cf9a53048a5c083eedc005dcdb5cc768924ae",
    ),
    "5976069": (
        159714548,
        "ed40f7e418d10484091b059703eeb95ae3199fe042891dcec4be6696b9968374",
    ),
    "5976066": (
        161711007,
        "87700668ae45d45d5ca1ef6ae9bd81ab0f5ec88cc95dcef9ae7838f727a13aa6",
    ),
    "5976063": (
        158418861,
        "48143ac703cbe33299f7ae9f4995db49a258690f60e5debbff8995c34841c7f5",
    ),
    "5976060": (
        149356640,
        "dfcb0d658311481523c6e6ca0c3f5a3e1d3d12cde5d7a8ce629a9006ec7dbb39",
    ),
}


def read_topics(path: Path) -> tuple[dict[int, set[bytes]], list[bytes]]:
    assignments: dict[int, set[bytes]] = {}
    topics: set[bytes] = set()
    with gzip.open(path, "rb") as source:
        for line in source:
            topic, raw_id, relevance = line.split()
            document_id = int(raw_id)
            labels = assignments.setdefault(document_id, set())
            if relevance != b"1" or topic in labels:
                raise ValueError(f"Invalid topic assignment for document {document_id}")
            labels.add(topic)
            topics.add(topic)
    if len(topics) != 103:
        raise ValueError(f"Expected 103 topics, found {len(topics)}")
    return assignments, sorted(topics)


def write_split(
    output: Path,
    name: str,
    inputs: Sequence[Path],
    expected_rows: int,
    assignments: dict[int, set[bytes]],
    label_ids: dict[bytes, int],
) -> None:
    rows = 0
    with (
        (output / f"{name}.libsvm.gz").open("wb") as archive,
        gzip.GzipFile(
            fileobj=archive, filename="", mode="wb", mtime=0, compresslevel=1
        ) as vectors,
        (output / f"{name}-documents.csv").open("wb") as documents,
    ):
        documents.write(b"document_id\n")
        for path in inputs:
            with gzip.open(path, "rb") as source:
                for line in source:
                    fields = line.split(maxsplit=1)
                    document_id = int(fields[0])
                    labels = assignments.pop(document_id, None)
                    if labels is None:
                        raise ValueError(
                            f"Document {document_id} is repeated or has no topics"
                        )
                    label_field = ",".join(
                        str(label_ids[topic]) for topic in sorted(labels)
                    )
                    features = b" " + fields[1].rstrip() if len(fields) == 2 else b""
                    vectors.write(label_field.encode("ascii") + features + b"\n")
                    documents.write(fields[0] + b"\n")
                    rows += 1
    if rows != expected_rows:
        raise ValueError(f"Expected {expected_rows} {name} rows, found {rows}")


def prepare(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(output)
    for name, (size, expected_digest) in SOURCES.items():
        path = source / name
        if path.stat().st_size != size:
            raise ValueError(f"Unexpected size for {path}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected_digest:
            raise ValueError(f"Unexpected SHA-256 for {path}")

    assignments, topics = read_topics(source / "5976048")
    label_ids = {topic: index for index, topic in enumerate(topics)}
    with TemporaryDirectory(dir=output.parent) as temporary:
        prepared = Path(temporary) / "prepared"
        prepared.mkdir()
        write_split(
            prepared,
            "train",
            [source / "5976057"],
            23149,
            assignments,
            label_ids,
        )
        write_split(
            prepared,
            "test",
            [source / name for name in ("5976069", "5976066", "5976063", "5976060")],
            781265,
            assignments,
            label_ids,
        )
        if assignments:
            raise ValueError(f"Topic assignments without vectors: {len(assignments)}")
        with (prepared / "topics.csv").open("wb") as labels:
            labels.write(b"label_id,topic\n")
            for topic, index in label_ids.items():
                labels.write(f"{index},".encode("ascii") + topic + b"\n")
        prepared.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
