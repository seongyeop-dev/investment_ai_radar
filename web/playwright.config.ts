import { defineConfig } from "@playwright/test";

const baseURL = "http://127.0.0.1:4173";
const serverIsManagedByLauncher =
  process.env.PLAYWRIGHT_EXTERNAL_WEB_SERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: "temp/frz006-artifacts/test-results",
  use: {
    baseURL,
    channel: "chrome",
    viewport: {
      width: 1280,
      height: 900,
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  webServer: serverIsManagedByLauncher
    ? undefined
    : {
        command:
          "node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 4173",
        url: `${baseURL}/sources`,
        reuseExistingServer: false,
        timeout: 120_000,
        env: {
          NEXT_DIST_DIR: "temp/frz006-next",
          NEXT_PUBLIC_API_BASE_URL:
            "http://127.0.0.1:4173/__frz006_api",
        },
      },
});
