{ pkgs, ... }:

{
  packages = [
    pkgs.jq
    pkgs.julia
    pkgs.ruff
    pkgs.zlib
    (pkgs.rWrapper.override {
      packages = with pkgs.rPackages; [
        curl
        digest
        filelock
        jsonlite
        testthat
      ];
    })
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

  enterTest = ''
    dm_repo_root="$PWD"
    cd packages/python
    ${pkgs.ruff}/bin/ruff format --check . ../../tools
    ${pkgs.ruff}/bin/ruff check . ../../tools
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
    diff registry/releases/2026.09/index.json packages/cli/assets/index.json
    diff registry/releases/2026.09/selector.json packages/cli/assets/selector.json
    for schema in index manifest erratum selector catalog; do
      diff "spec/schema/''${schema}-v1.schema.json" \
        "packages/cli/assets/''${schema}-v1.schema.json"
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
  '';
}
