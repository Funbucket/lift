#!/usr/bin/env node
import { spawn } from "node:child_process";
import { stderr as output } from "node:process";
import { dirname, resolve } from "node:path";
import { text } from "@clack/prompts";

function parseArgs(argv) {
  const [command, provider, ...rest] = argv;
  const options = {};
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index];
    if (!token.startsWith("--")) continue;
    options[token.slice(2)] = rest[index + 1];
    index += 1;
  }
  return { command, provider, options };
}

function getOpenCommand(url) {
  if (process.platform === "darwin") return { command: "open", args: [url] };
  if (process.platform === "win32") return { command: "cmd", args: ["/c", "start", "", url] };
  return { command: "xdg-open", args: [url] };
}

function openUrl(url) {
  try {
    const command = getOpenCommand(url);
    const child = spawn(command.command, command.args, {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.unref();
    return true;
  } catch {
    return false;
  }
}

async function main() {
  const { command, provider, options } = parseArgs(process.argv.slice(2));
  if (command !== "login" || !provider || !options["auth-path"]) {
    throw new Error("Usage: pi-auth-bridge.mjs login <provider> --auth-path <path> [--settings-path <path>]");
  }

  const { AuthStorage, ModelRegistry } = await import("@mariozechner/pi-coding-agent");
  const authPath = resolve(options["auth-path"]);
  const modelsJsonPath = resolve(dirname(authPath), "models.json");
  const authStorage = AuthStorage.create(authPath);

  await authStorage.login(provider, {
    onAuth: (info) => {
      const opened = openUrl(info.url);
      output.write(opened ? "Opened login URL in your browser.\n" : "Open this login URL manually.\n");
      output.write(`Auth URL: ${info.url}\n`);
      if (info.instructions) output.write(`${info.instructions}\n`);
    },
    onPrompt: async (prompt) => text({
      message: prompt.message,
      placeholder: prompt.placeholder ?? "",
      initialValue: prompt.placeholder ?? "",
    }),
    onProgress: (message) => output.write(`${message}\n`),
    onManualCodeInput: async () => text({
      message: "Paste redirect URL or auth code",
      placeholder: "",
    }),
  });

  const registry = ModelRegistry.create(AuthStorage.create(authPath), modelsJsonPath);
  const models = registry
    .getAvailable()
    .filter((model) => model.provider === provider)
    .map((model) => model.id);

  process.stdout.write(JSON.stringify({
    status: "ok",
    provider,
    models,
    default_model: models[0] ?? null,
  }) + "\n");
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({
    status: "error",
    message: error instanceof Error ? error.message : String(error),
  }) + "\n");
  process.exitCode = 1;
});
