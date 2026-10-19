# Datamonger C ABI

This crate builds `datamonger_ffi`, a shared library for Julia and other C
callers. It uses the local `datamonger-core` dependency. Registry resolution,
retrieval, artifact integrity, cache leases, metadata, and host return types
remain the client's responsibility.

[`include/datamonger.h`](include/datamonger.h) defines ABI 1, including layouts,
tags, errors, and ownership. A breaking layout, tag, or ownership change requires
a new ABI version and corresponding Julia bindings. The library exports
`dm_abi_version()` so clients reject incompatible libraries before passing data.

Decoder calls accept verified artifact paths, declared compression, and typed
recipes. Canonical calls accept typed logical components, including dense
matrices, and stream SHA-256 without retaining canonical bytes unless requested.
The Julia adapter validates the complete revision 1 recipe before entering the
ABI. This ABI uses Julia's numeric compatibility: a nonzero decimal that rounds
to zero raises a decode error, while nonzero subnormals remain valid. Core users
retain the default conversion behavior unless they request this option.

Inputs are borrowed for the call and never retained. All buffers must be aligned,
readable, and immutable, and lengths must describe their accessible storage.
The bridge checks null pointers, alignment, lengths, UTF-8, validity bytes, and
logical structure; it cannot validate that an arbitrary address is readable.
Strings are UTF-8 with explicit byte lengths, so values may contain NUL bytes.
Sparse indices and row offsets are zero-based, and dense values use row order.

Every operation returns one owned result, including errors and caught Rust
panics. Result accessors borrow immutable views until `dm_result_free()`.
Callers must copy those views before freeing the result, free it exactly once,
and never free individual buffers. Independent calls may run concurrently.
Accessors and freeing require a live result handle or NULL. Invalid pointers,
use after free, and double free violate the caller's safety obligations.

From the repository's devenv shell:

```console
dm-core-cargo fmt --manifest-path crates/datamonger-ffi/Cargo.toml --check
dm-core-cargo clippy --locked --manifest-path crates/datamonger-ffi/Cargo.toml --all-targets -- -D warnings
dm-core-cargo test --locked --manifest-path crates/datamonger-ffi/Cargo.toml
julia tools/dm_julia_core.jl
```

The Julia differential suite exercises these layouts, all logical types,
compressed artifacts, error mapping, and copied-buffer lifetimes against its
independent test oracle and the shared corpus. The C smoke test also compiles
and exercises the public header. CI builds and tests native distributions for
all supported Julia platforms; see `CONTRIBUTING.md` and `OPERATIONS.md`.
