{ pkgs, inputs, ... }:

let
  corePkgs = pkgs.extend (import inputs.rust-overlay);
  workspaceRust = corePkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
  coreRust = corePkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain-msrv.toml;
in
{
  packages = [
    inputs.diplodocus.packages.${pkgs.stdenv.hostPlatform.system}.default
    pkgs.go-task
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
      files = "^(\\.github/.*\\.ya?ml|devenv\\.yaml|Taskfile\\.yml)$";
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

  env.DM_RUFF = "${pkgs.ruff}/bin/ruff";
  env.DM_CORE_CARGO = "${workspaceRust}/bin/cargo";
  env.DM_CORE_RUSTC = "${coreRust}/bin/rustc";

  scripts.dm-core-cargo = {
    description = "Run Cargo with the core library's minimum Rust toolchain";
    exec = ''
      export PATH="${coreRust}/bin:$PATH"
      export RUSTC="${coreRust}/bin/rustc"
      export RUSTDOC="${coreRust}/bin/rustdoc"
      exec "${workspaceRust}/bin/cargo" "$@"
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

  enterTest = "task test";
}
