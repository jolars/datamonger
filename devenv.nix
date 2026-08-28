{ pkgs, ... }:

{
  packages = [ pkgs.ruff ];

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

  enterTest = ''
    cd packages/python
    uv run ruff format --check . ../../tools
    uv run ruff check . ../../tools
    uv run mypy
    uv run pytest
    uv run python ../../tools/build_proof_index.py --check
    uv build
  '';
}
