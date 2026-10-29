{ pkgs, inputs, ... }:

let
  corePkgs = pkgs.extend (import inputs.rust-overlay);
  coreRust = corePkgs.rust-bin.fromRustupToolchainFile ./crates/datamonger-core/rust-toolchain.toml;
in
{
  packages = [
    inputs.diplodocus.packages.${pkgs.stdenv.hostPlatform.system}.default
    pkgs.jq
    pkgs.julia
    pkgs.pandoc
    pkgs.ruff
    pkgs.cargo-msrv
    pkgs.xz
  ];

  git-hooks.hooks = {
    nixfmt.enable = true;
    ruff = {
      enable = true;
      files = "^(packages/python/|tools/|curation/).*\\.py$";
    };
    ruff-format = {
      enable = true;
      files = "^(packages/python/|tools/|curation/).*\\.py$";
    };
    prettier = {
      enable = true;
      types = [ "file" ];
      files = "^(\\.github/.*\\.ya?ml|devenv\\.yaml)$";
    };
  };

  languages.python = {
    enable = true;
    directory = "./packages/python";
    manylinux.enable = true;
    venv.enable = true;
    uv = {
      enable = true;
      sync = {
        enable = true;
        allGroups = true;
      };
    };
  };

  languages.rust = {
    enable = true;
    toolchainFile = ./rust-toolchain.toml;
  };

  languages.r = {
    enable = true;
    package = (
      pkgs.rWrapper.override {
        packages = with pkgs.rPackages; [
          curl
          digest
          filelock
          jsonlite
          pkgload
          evaluate
          knitr
          rmarkdown
          testthat
          devtools
          rextendr
        ];
      }
    );
  };

  env.DM_CORE_CARGO = "${coreRust}/bin/cargo";
  env.DM_CORE_RUSTC = "${coreRust}/bin/rustc";

  scripts.dm-core-cargo = {
    description = "Run Cargo with the core library's minimum Rust toolchain";
    exec = ''
      export PATH="${coreRust}/bin:$PATH"
      export RUSTC="${coreRust}/bin/rustc"
      export RUSTDOC="${coreRust}/bin/rustdoc"
      exec "${coreRust}/bin/cargo" "$@"
    '';
  };

  tasks."r:catalog" = {
    description = "Refresh the compressed R catalog from the bundled registry";
    after = [ "devenv:python:uv" ];
    wantedBy = [ ];
    exec = ''
      cd "$DEVENV_ROOT"
      uv run --project packages/python python tools/dm_bundle_registry.py --refresh-r
    '';
  };

  tasks."r:vendor" = {
    description = "Vendor the R package's published Rust dependencies";
    after = [ "r:catalog" ];
    wantedBy = [ ];
    exec = ''
      set -euo pipefail
      cd "$DEVENV_ROOT"
      dm-core-cargo metadata --manifest-path packages/r/src/rust/Cargo.toml --format-version 1 > /dev/null
      Rscript -e 'rextendr::vendor_crates("packages/r", overwrite = TRUE, clean = TRUE)'
      python "$DEVENV_ROOT/tools/dm_rust_sources.py" --record-vendor
    '';
  };

  scripts.dm-local-r = {
    description = "Run Rscript against the local Rust core";
    exec = ''
      set -euo pipefail
      python "$DEVENV_ROOT/tools/dm_r_local.py" "$@"
    '';
  };

  scripts.dm-test-r = {
    description = "Test the R adapter against the local Rust core";
    exec = ''
      cd "$DEVENV_ROOT"
      dm-local-r -e 'pkgbuild::compile_dll("packages/r", debug = TRUE, force = TRUE); testthat::test_local("packages/r")'
    '';
  };

  scripts.dm-bundle-registry = {
    description = "Bundle a published registry release in all clients";
    exec = ''
      uv run --project "$DEVENV_ROOT/packages/python" python "$DEVENV_ROOT/tools/dm_bundle_registry.py" "$@"
    '';
  };

  enterTest = ''
    dm_repo_root="$PWD"
    cd packages/python
    ${pkgs.ruff}/bin/ruff format --check . ../../tools ../../curation
    ${pkgs.ruff}/bin/ruff check . ../../tools ../../curation
    uv run mypy
    uv run pytest
    uv run python ../../tools/dm_index.py check
    uv run python ../../tools/dm_registry_release.py check
    uv run python ../../tools/dm_index.py check \
      tests/registry/releases/test-0001/release.yaml
    uv run python ../../tools/dm_index.py check \
      tests/registry/releases/test-0002/release.yaml
    uv build
    cargo fmt --check
    cargo clippy --locked --all-targets -- -D warnings
    cd "$dm_repo_root"
    python tools/dm_rust_sources.py --check
    dm-core-cargo fmt --manifest-path crates/datamonger-core/Cargo.toml --check
    dm-core-cargo clippy --manifest-path crates/datamonger-core/Cargo.toml \
      --locked --all-targets -- -D warnings
    dm-core-cargo test --manifest-path crates/datamonger-core/Cargo.toml --locked
    dm-core-cargo fmt --manifest-path crates/datamonger-ffi/Cargo.toml --check
    dm-core-cargo clippy --manifest-path crates/datamonger-ffi/Cargo.toml \
      --locked --all-targets -- -D warnings
    dm-core-cargo test --manifest-path crates/datamonger-ffi/Cargo.toml --locked
    julia tools/dm_julia_core.jl
    dm_abi_binary="$(mktemp)"
    cc -Wall -Wextra -Werror -I crates/datamonger-ffi/include \
      crates/datamonger-ffi/tests/abi.c \
      -L crates/datamonger-ffi/target/release -ldatamonger_ffi \
      -Wl,-rpath,"$dm_repo_root/crates/datamonger-ffi/target/release" \
      -o "$dm_abi_binary"
    "$dm_abi_binary" tests/conformance/artifacts/small.libsvm
    rm "$dm_abi_binary"
    dm-core-cargo fmt --manifest-path packages/r/src/rust/Cargo.toml --check
    dm-core-cargo clippy --manifest-path packages/r/src/rust/Cargo.toml \
      --locked --all-targets -- -D warnings
    uv run --project packages/python python tools/dm_bundle_registry.py --check
    for schema in index manifest erratum selector catalog; do
      diff "spec/schema/''${schema}-v1.schema.json" \
        "packages/cli/assets/''${schema}-v1.schema.json"
    done
    for version in 2 3 4 5; do
      for schema in index manifest; do
        diff "spec/schema/''${schema}-v''${version}.schema.json" \
          "packages/cli/assets/''${schema}-v''${version}.schema.json"
      done
    done
    cd packages/cli
    cargo fmt --check
    cargo clippy --locked --all-targets -- -D warnings
    cargo test --locked
    cargo run --locked --example generate_cli_docs -- --check
    cd "$dm_repo_root"
    ${pkgs.diffutils}/bin/diff -r \
      tests/conformance packages/r/tests/testthat/fixtures/conformance
    ${pkgs.diffutils}/bin/diff -r \
      tests/conformance packages/julia/test/fixtures/conformance
    ${pkgs.julia}/bin/julia --project=packages/julia -e \
      'using Pkg; Pkg.instantiate(); Pkg.test()'
    dm_r_check_dir="$(mktemp -d)"
    trap 'rm -rf "$dm_r_check_dir"' EXIT
    cd "$dm_r_check_dir"
    R CMD build "$dm_repo_root/packages/r"
    _R_CHECK_CRAN_INCOMING_REMOTE_=false \
      R CMD check --no-manual --as-cran datamonger_*.tar.gz
    cd "$dm_repo_root"
    dm-test-r
  '';
}
