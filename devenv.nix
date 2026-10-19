{ pkgs, inputs, ... }:

let
  corePkgs = pkgs.extend (import inputs.rust-overlay);
  coreRust = corePkgs.rust-bin.fromRustupToolchainFile ./crates/datamonger-core/rust-toolchain.toml;
in
{
  packages = [
    pkgs.jq
    pkgs.julia
    pkgs.pandoc
    pkgs.ruff
    pkgs.cargo-msrv
    pkgs.xz
  ];

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

  scripts.dm-vendor-r = {
    description = "Vendor the R package's published Rust dependencies";
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
      dm_r_lock="$DEVENV_ROOT/packages/r/src/rust/Cargo.lock"
      dm_r_saved_lock="$(mktemp)"
      cp "$dm_r_lock" "$dm_r_saved_lock"
      trap 'cp "$dm_r_saved_lock" "$dm_r_lock"; rm -f "$dm_r_saved_lock"' EXIT
      export DM_R_CORE_PATH="$DEVENV_ROOT/crates/datamonger-core"
      export DEBUG=1
      Rscript "$@"
    '';
  };

  scripts.dm-test-r = {
    description = "Test the R adapter against the local Rust core";
    exec = ''
      cd "$DEVENV_ROOT"
      dm-local-r -e 'pkgbuild::compile_dll("packages/r", debug = TRUE, force = TRUE); testthat::test_local("packages/r")'
    '';
  };

  scripts.dm-document-r = {
    description = "Regenerate private R wrappers from extendr metadata";
    exec = ''
      cd "$DEVENV_ROOT/packages/r"
      dm-local-r tools/document.R
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
    cd "$dm_repo_root"
    python tools/dm_rust_sources.py --check
    dm-core-cargo fmt --manifest-path crates/datamonger-core/Cargo.toml --check
    dm-core-cargo clippy --manifest-path crates/datamonger-core/Cargo.toml \
      --locked --all-targets -- -D warnings
    dm-core-cargo test --manifest-path crates/datamonger-core/Cargo.toml --locked
    dm-core-cargo fmt --manifest-path packages/r/src/rust/Cargo.toml --check
    dm-core-cargo clippy --manifest-path packages/r/src/rust/Cargo.toml \
      --locked --all-targets -- -D warnings
    uv run --project packages/python python tools/dm_bundle_registry.py --check
    for schema in index manifest erratum selector catalog; do
      diff "spec/schema/''${schema}-v1.schema.json" \
        "packages/cli/assets/''${schema}-v1.schema.json"
    done
    for version in 2 3; do
      for schema in index manifest; do
        diff "spec/schema/''${schema}-v''${version}.schema.json" \
          "packages/cli/assets/''${schema}-v''${version}.schema.json"
      done
    done
    cd packages/cli
    cargo fmt --check
    cargo clippy --locked --all-targets -- -D warnings
    cargo test --locked
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
