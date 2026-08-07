import { spawn, spawnSync } from "node:child_process";
import { request } from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = 4173;
const baseURL = `http://${host}:${port}`;
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const nextCli = join(projectRoot, "node_modules", "next", "dist", "bin", "next");
const playwrightCli = join(
  projectRoot,
  "node_modules",
  "@playwright",
  "test",
  "cli.js",
);

let serverProcess;
let testProcess;
let cleanupStarted = false;

function isServerAvailable() {
  return new Promise((resolveAvailable) => {
    const req = request(`${baseURL}/sources`, { method: "GET" }, (response) => {
      response.resume();
      resolveAvailable(
        response.statusCode !== undefined && response.statusCode < 500,
      );
    });
    req.setTimeout(1_000, () => req.destroy());
    req.on("error", () => resolveAvailable(false));
    req.end();
  });
}

function waitForClose(child, timeoutMs) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve(true);
  }
  return new Promise((resolveClosed) => {
    const onClose = () => {
      clearTimeout(timer);
      resolveClosed(true);
    };
    const timer = setTimeout(() => {
      child.off("close", onClose);
      resolveClosed(false);
    }, timeoutMs);
    child.once("close", onClose);
  });
}

async function waitForServer(child, timeoutMs) {
  await new Promise((resolveReady, rejectReady) => {
    let output = "";
    const cleanup = () => {
      clearTimeout(timer);
      child.stdout.off("data", onStdout);
      child.off("close", onClose);
    };
    const onStdout = async (data) => {
      output += data.toString();
      if (!output.includes("Ready in")) return;
      cleanup();
      if (await isServerAvailable()) {
        resolveReady();
      } else {
        rejectReady(new Error(`Next reported ready but ${baseURL} is unavailable.`));
      }
    };
    const onClose = (code, signal) => {
      cleanup();
      rejectReady(
        new Error(
          `Next test server exited before readiness (code=${code}, signal=${signal}).`,
        ),
      );
    };
    const timer = setTimeout(() => {
      cleanup();
      rejectReady(
        new Error(`Timed out waiting ${timeoutMs}ms for ${baseURL}/sources.`),
      );
    }, timeoutMs);
    child.stdout.on("data", onStdout);
    child.once("close", onClose);
  });
}

function forceKillOwnedTree(pid) {
  if (!pid) return;
  if (process.platform === "win32") {
    const systemRoot = process.env.SystemRoot || "C:\\Windows";
    const taskkill = join(systemRoot, "System32", "taskkill.exe");
    const result = spawnSync(
      taskkill,
      ["/PID", String(pid), "/T", "/F"],
      { encoding: "utf8", windowsHide: true },
    );
    if (result.status !== 0 && result.stderr) {
      process.stderr.write(result.stderr);
    }
    return;
  }
  try {
    process.kill(pid, "SIGKILL");
  } catch {
    // The owned process has already exited.
  }
}

async function stopOwnedServer() {
  if (cleanupStarted || !serverProcess) return;
  cleanupStarted = true;
  const pid = serverProcess.pid;
  console.log(`[e2e-server] stopping pid=${pid}`);

  if (
    serverProcess.exitCode === null &&
    serverProcess.signalCode === null
  ) {
    serverProcess.kill("SIGTERM");
  }
  if (!(await waitForClose(serverProcess, 5_000))) {
    console.warn(`[e2e-server] graceful stop timed out; killing owned pid=${pid}`);
    forceKillOwnedTree(pid);
    if (!(await waitForClose(serverProcess, 5_000))) {
      throw new Error(`Owned Next test server pid=${pid} did not exit.`);
    }
  }
  if (await isServerAvailable()) {
    throw new Error(`Owned Next test server stopped but ${baseURL} is still active.`);
  }
  console.log(`[e2e-server] stopped pid=${pid}`);
}

function waitForTestExit(child) {
  return new Promise((resolveExit, rejectExit) => {
    child.once("error", rejectExit);
    child.once("close", (code, signal) => resolveExit({ code, signal }));
  });
}

function buildProductionBundle(env) {
  console.log("[e2e-build] starting");
  const result = spawnSync(process.execPath, [nextCli, "build"], {
    cwd: projectRoot,
    env,
    shell: false,
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.signal) {
    throw new Error(
      `Next production build exited with signal=${result.signal}.`,
    );
  }
  if (result.status !== 0) {
    throw new Error(
      `Next production build failed with code=${result.status}.`,
    );
  }
  console.log("[e2e-build] complete");
}

async function main() {
  if (await isServerAvailable()) {
    throw new Error(`${baseURL} is already in use.`);
  }

  const serverEnv = {
    ...process.env,
    NEXT_DIST_DIR: "temp/frz006-next",
    NEXT_PUBLIC_API_BASE_URL: `${baseURL}/__frz006_api`,
  };
  buildProductionBundle(serverEnv);

  serverProcess = spawn(
    process.execPath,
    [nextCli, "start", "--hostname", host, "--port", String(port)],
    {
      cwd: projectRoot,
      env: serverEnv,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  console.log(`[e2e-server] started pid=${serverProcess.pid}`);
  serverProcess.stdout.pipe(process.stdout);
  serverProcess.stderr.pipe(process.stderr);

  await waitForServer(serverProcess, 120_000);
  console.log(`[e2e-server] ready pid=${serverProcess.pid}`);

  testProcess = spawn(
    process.execPath,
    [playwrightCli, "test", ...process.argv.slice(2)],
    {
      cwd: projectRoot,
      env: {
        ...process.env,
        PLAYWRIGHT_EXTERNAL_WEB_SERVER: "1",
      },
      shell: false,
      stdio: "inherit",
      windowsHide: true,
    },
  );
  console.log(`[e2e-runner] started pid=${testProcess.pid}`);
  const result = await waitForTestExit(testProcess);
  if (result.signal) {
    console.error(`[e2e-runner] exited with signal=${result.signal}`);
    return 1;
  }
  return result.code ?? 1;
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (testProcess && testProcess.exitCode === null) {
      testProcess.kill(signal);
    }
  });
}

process.once("exit", () => {
  if (
    serverProcess?.pid &&
    serverProcess.exitCode === null &&
    serverProcess.signalCode === null
  ) {
    forceKillOwnedTree(serverProcess.pid);
  }
});

let exitCode = 1;
try {
  exitCode = await main();
} catch (error) {
  console.error(error instanceof Error ? error.stack : error);
} finally {
  try {
    await stopOwnedServer();
  } catch (error) {
    console.error(error instanceof Error ? error.stack : error);
    exitCode = 1;
  }
}
process.exitCode = exitCode;
