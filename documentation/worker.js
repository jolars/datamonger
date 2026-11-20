const repository = "jolars/datamonger";
const installer = "datamonger-installer.sh";
const stableCliTag = /^datamonger-v\d+\.\d+\.\d+$/;

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== "/install") {
      return env.ASSETS.fetch(request);
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
    }

    try {
      for (let page = 1; ; page += 1) {
        const response = await fetch(
          `https://api.github.com/repos/${repository}/releases?per_page=100&page=${page}`,
          {
            headers: {
              Accept: "application/vnd.github+json",
              "User-Agent": "datamonger.dev",
            },
            cf: { cacheEverything: true, cacheTtlByStatus: { "200": 300, "400-599": 0 } },
          },
        );
        if (!response.ok) {
          break;
        }

        const releases = await response.json();
        const release = releases.find(
          (candidate) =>
            !candidate.draft &&
            !candidate.prerelease &&
            stableCliTag.test(candidate.tag_name) &&
            candidate.assets.some((asset) => asset.name === installer),
        );
        if (release) {
          return new Response(null, {
            status: 302,
            headers: {
              Location: `https://github.com/${repository}/releases/download/${release.tag_name}/${installer}`,
              "Cache-Control": "public, max-age=300",
            },
          });
        }
        if (releases.length < 100) {
          return new Response("No stable CLI installer is available yet.\n", { status: 404 });
        }
      }
    } catch (error) {
      console.error("Could not look up CLI releases", error);
    }
    return new Response("Could not look up the CLI installer.\n", { status: 502 });
  },
};
