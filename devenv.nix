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
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy
    uv run pytest
    uv build
  '';
}
