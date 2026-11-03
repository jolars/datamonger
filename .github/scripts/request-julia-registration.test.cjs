const { test } = require("node:test");
const assert = require("node:assert/strict");
const request = require("./request-julia-registration.cjs");
const target = {
  path: "packages/julia",
  version: "0.1.0",
  tag: "datamonger-julia-v0.1.0",
  sha: "a".repeat(40),
  notes: "Reviewed release notes.",
};
function setup() {
  const comments = [];
  const sent = [];
  const listCommentsForCommit = () => {};
  const github = {
    paginate: async (method, input) => {
      assert.equal(method, listCommentsForCommit);
      assert.equal(input.commit_sha, target.sha);
      return comments;
    },
    rest: {
      repos: {
        listCommentsForCommit,
        createCommitComment: async (input) => {
          sent.push(input);
          comments.push({
            user: { login: "github-actions[bot]" },
            body: input.body,
          });
        },
      },
    },
  };
  return {
    comments,
    sent,
    github,
    run: (targets = [target], retry = false) =>
      request({
        github,
        context: { repo: { owner: "jolars", repo: "datamonger" } },
        core: { info() {} },
        targets,
        retry,
      }),
  };
}
test("requests the saved Julia commit and reviewed notes once across reruns", async () => {
  const { run, sent } = setup();
  await run();
  await run();
  assert.equal(sent.length, 1);
  assert.equal(sent[0].commit_sha, target.sha);
  assert.match(
    sent[0].body,
    /^@JuliaRegistrator register subdir=packages\/julia\n/,
  );
  assert.ok(sent[0].body.includes(target.notes));
});
test("retries the same saved commit explicitly", async () => {
  const { run, sent } = setup();
  await run();
  await run([target], true);
  assert.deepEqual(sent[0], sent[1]);
});
test("ignores other packages and tolerates no pending Julia registration", async () => {
  const { run, sent } = setup();
  await run([]);
  await run([{ path: "packages/python" }]);
  assert.equal(sent.length, 0);
});
test("validates the immutable commit, tag, and release notes", async () => {
  const { run, sent } = setup();
  for (const invalid of [
    { sha: "main" },
    { tag: "datamonger-v0.1.0" },
    { notes: "" },
  ]) {
    await assert.rejects(
      run([{ ...target, ...invalid }]),
      /Invalid Julia release target/,
    );
  }
  assert.equal(sent.length, 0);
});
test("does not trust duplicate markers posted by another user", async () => {
  const { run, sent, comments } = setup();
  await run();
  comments[0].user.login = "someone-else";
  await run();
  assert.equal(sent.length, 2);
});
test("propagates API failures for workflow retries", async () => {
  const { run, github } = setup();
  github.rest.repos.createCommitComment = async () => {
    throw new Error("GitHub unavailable");
  };
  await assert.rejects(run(), /GitHub unavailable/);
});
