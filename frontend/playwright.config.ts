import { defineConfig } from "@playwright/test";

// ADR 033: smoke test only. Prod build, not `next dev` — dev-only warnings would
// drown the console-error check that is the whole point.
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:3000" },
  webServer: {
    // next.config sets output: "standalone", so `next start` is not what production
    // runs — the Dockerfile runs this server.js, with static/ and public/ beside it.
    command:
      "rm -rf .next/standalone/.next/static .next/standalone/public && cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/ && node .next/standalone/server.js",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    // server.js binds to $HOSTNAME, and Docker sets that to the container id — so
    // in CI it listened on a hostname nobody could reach and the port stayed shut.
    env: { HOSTNAME: "0.0.0.0", PORT: "3000" },
    stdout: "pipe", // otherwise a server that dies at boot leaves only a timeout
  },
});
