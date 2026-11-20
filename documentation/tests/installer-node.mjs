import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "../worker.js";

const install = new Request("https://datamonger.dev/install");
const installer = { name: "datamonger-installer.sh" };

test("redirects to a stable CLI installer past unrelated releases", async (t) => {
  const releases = [
    { tag_name: "registry-v2.0.0", assets: [] },
    { tag_name: "datamonger-python-v1.2.0", assets: [] },
    { tag_name: "datamonger-v1.2.0-rc.1", prerelease: true, assets: [installer] },
    { tag_name: "datamonger-v1.1.0", draft: true, assets: [installer] },
    { tag_name: "datamonger-v1.0.0", assets: [] },
  ];
  t.mock.method(globalThis, "fetch", async (url) => {
    const page = new URL(url).searchParams.get("page");
    return Response.json(
      page === "1"
        ? [...releases, ...Array(95).fill(releases[0])]
        : [{ tag_name: "datamonger-v0.9.0", assets: [installer] }],
    );
  });

  const response = await worker.fetch(install, {});
  assert.equal(response.status, 302);
  assert.equal(
    response.headers.get("Location"),
    "https://github.com/jolars/datamonger/releases/download/datamonger-v0.9.0/datamonger-installer.sh",
  );
  assert.equal(globalThis.fetch.mock.callCount(), 2);
});

test("returns an error when the installer is unavailable", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json([]));
  assert.equal((await worker.fetch(install, {})).status, 404);

  globalThis.fetch.mock.mockImplementation(async () => new Response(null, { status: 429 }));
  assert.equal((await worker.fetch(install, {})).status, 502);
});

test("serves the existing site through the static asset binding", async () => {
  const request = new Request("https://datamonger.dev/datasets/");
  const env = {
    ASSETS: {
      fetch(received) {
        assert.equal(received, request);
        return new Response("dataset browser");
      },
    },
  };
  assert.equal(await (await worker.fetch(request, env)).text(), "dataset browser");
});
