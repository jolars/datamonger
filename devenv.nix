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
    ${pkgs.ruff}/bin/ruff format --check . ../../tools
    ${pkgs.ruff}/bin/ruff check . ../../tools
    uv run mypy
    uv run pytest
    uv run python ../../tools/dm_index.py check
    uv run python ../../tools/dm_index.py check \
      tests/registry/releases/test-0001/release.yaml
    uv run python ../../tools/dm_index.py check \
      tests/registry/releases/test-0002/release.yaml
    uv build
  '';
}
