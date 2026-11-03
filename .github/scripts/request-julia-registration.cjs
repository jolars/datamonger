module.exports = async function requestJuliaRegistration({
  github,
  context,
  core,
  targets,
  retry = false,
}) {
  if (!Array.isArray(targets)) {
    throw new Error("Versionary did not supply external release targets.");
  }
  const juliaTargets = targets.filter(
    (target) => target.path === "packages/julia",
  );
  for (const target of juliaTargets) {
    if (
      !/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(target.sha) ||
      typeof target.version !== "string" ||
      !target.version ||
      target.tag !== `datamonger-julia-v${target.version}` ||
      typeof target.notes !== "string" ||
      !target.notes.trim()
    ) {
      throw new Error("Invalid Julia release target.");
    }
    const marker =
      "<!-- versionary:registrator " +
      JSON.stringify([target.path, target.version, target.sha]) +
      " -->";
    const comments = await github.paginate(
      github.rest.repos.listCommentsForCommit,
      {
        ...context.repo,
        commit_sha: target.sha,
        per_page: 100,
      },
    );
    const requested = comments.some(
      (comment) =>
        comment.user?.login === "github-actions[bot]" &&
        comment.body?.includes(marker),
    );
    if (requested && !retry) {
      core.info(`Registration was already requested for ${target.tag}.`);
      continue;
    }
    await github.rest.repos.createCommitComment({
      ...context.repo,
      commit_sha: target.sha,
      body:
        "@JuliaRegistrator register subdir=packages/julia" +
        "\n\nRelease notes:\n\n" +
        target.notes +
        "\n\n" +
        marker,
    });
    core.info(`Requested registration for ${target.tag} at ${target.sha}.`);
  }
};
