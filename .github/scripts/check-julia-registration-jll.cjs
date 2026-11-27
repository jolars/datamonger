const { execFileSync } = require("node:child_process");
const { mkdtempSync, rmSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

module.exports = function checkJuliaRegistrationJll(sha) {
  const directory = mkdtempSync(join(tmpdir(), "datamonger-registration-"));
  const checkout = join(directory, "checkout");
  try {
    execFileSync("git", ["worktree", "add", "--detach", checkout, sha], {
      stdio: "inherit",
    });
    const env = { ...process.env };
    delete env.DM_JULIA_CORE_LIBRARY;
    try {
      execFileSync(
        "julia",
        [
          "--startup-file=no",
          "--project=packages/julia",
          "-e",
          "using Pkg; Pkg.instantiate(); using Datamonger; " +
            "isdefined(Datamonger, :_supports_sparse_label_join) && " +
            "!Datamonger._supports_sparse_label_join() && exit(42)",
        ],
        { cwd: checkout, env, stdio: "inherit" },
      );
      return true;
    } catch (error) {
      if (error.status === 42) return false;
      throw error;
    } finally {
      execFileSync("git", ["worktree", "remove", "--force", checkout], {
        stdio: "inherit",
      });
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
};
