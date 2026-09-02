# Datamonger conformance corpus

This directory is language-neutral test data. Paths in `cases.json` are
relative to this directory. A case is `active-python` when the current Python
reference client must execute it; `milestone-3` cases are normative vectors
whose client activation is deliberately deferred.

Each active decoder case supplies the complete version-1 recipe and expected
canonical SHA-256. A single-artifact case names one input path; an assembly case
maps each specified input role to its path. `canonical/cases.json` supplies
logical values and exact canonical bytes as lowercase hexadecimal, avoiding a
language-specific fixture serializer. `fuzz-regressions.json` stores minimized
byte inputs and their required failure stage. `errors.json` enumerates the
shared semantic failure cases and expected categories. Implementations may use
different native containers, exception types, and messages, but must agree on
logical values, canonical bytes, success or failure, and semantic failure
categories.
