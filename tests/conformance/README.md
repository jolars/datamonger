# Datamonger conformance corpus

This directory is language-neutral test data. Paths in `cases.json` are
relative to this directory. A case is `active-python` when the current Python
reference client must execute it; `milestone-3` cases are normative vectors
whose client activation is deliberately deferred.

Each active decoder case supplies the complete version-1 recipe and expected
canonical SHA-256. `canonical/cases.json` supplies logical values and exact
canonical bytes as lowercase hexadecimal, avoiding a language-specific fixture
serializer. `fuzz-regressions.json` stores minimized byte inputs and their
required failure stage. Implementations may use different native containers and
messages, but must agree on logical values, canonical bytes, and success or
failure.
