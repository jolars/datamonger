The source package bundles the Rust core and all Cargo dependencies. It builds
offline with Cargo and rustc 1.82.0 using at most two Cargo jobs. Installed
COPYRIGHTS contains crate authorship metadata and complete bundled license
notices.

The compiled-code check may note a reference to abort from the Rust standard
library's unrecoverable panic and allocation-failure handling. Datamonger
returns ordinary typed errors for decoder failures, and extendr catches
unwinding Rust panics at its R entry points. Standard Rust runtime behavior is
retained. Release builds remove Cargo intermediates after linking, following
the extendr packaging convention.

The current development version also produces the expected incoming-feasibility
note about its large version component.
