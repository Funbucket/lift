#!/usr/bin/env node
import { existsSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { mkdirSync } from "node:fs";
import {
  intro,
  isCancel,
  outro,
  select,
  text,
} from "@clack/prompts";

const OAUTH_PROVIDERS = [
  {
    id: "openai-codex",
    label: "ChatGPT Plus/Pro (Codex Subscription)",
  },
  {
    id: "anthropic-claude",
    label: "Claude Pro/Max",
  },
  {
    id: "github-copilot",
    label: "GitHub Copilot",
  },
];

const API_KEY_PROVIDERS = [
  {
    id: "openai",
    label: "OpenAI Platform API",
    envVar: "OPENAI_API_KEY",
    defaultModel: "gpt-5.4",
  },
  {
    id: "anthropic",
    label: "Anthropic API",
    envVar: "ANTHROPIC_API_KEY",
    defaultModel: "claude-sonnet-4-5",
  },
  {
    id: "google",
    label: "Google Gemini API",
    envVar: "GEMINI_API_KEY",
    defaultModel: "gemini-2.5-pro",
  },
];

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) continue;
    options[token.slice(2)] = argv[index + 1];
    index += 1;
  }
  return options;
}

function cancelled(value) {
  return isCancel(value);
}

function writeResult(path, payload) {
  if (!path) {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
    return;
  }
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const resultPath = options["result-path"];

  intro("Lift setup");

  const method = await select({
    message: "Choose how to configure model access:",
    options: [
      {
        value: "oauth",
        label: "OAuth login (recommended: ChatGPT Plus/Pro, Claude Pro/Max, Copilot, ...)",
      },
      {
        value: "api-key",
        label: "API key or custom provider (OpenAI, Anthropic, Google, ...)",
      },
      {
        value: "cancel",
        label: "Cancel",
      },
    ],
    initialValue: "oauth",
  });

  if (cancelled(method) || method === "cancel") {
    outro("Setup cancelled.");
    writeResult(resultPath, { status: "cancelled" });
    return;
  }

  if (method === "oauth") {
    const provider = await select({
      message: "Choose an OAuth provider to login:",
      options: OAUTH_PROVIDERS.map((entry) => ({
        value: entry.id,
        label: entry.label,
      })),
      initialValue: OAUTH_PROVIDERS[0].id,
    });
    if (cancelled(provider)) {
      outro("Setup cancelled.");
      writeResult(resultPath, { status: "cancelled" });
      return;
    }
    writeResult(resultPath, {
      status: "ok",
      method: "oauth",
      provider,
    });
    return;
  }

  const provider = await select({
    message: "Choose API-key provider:",
    options: API_KEY_PROVIDERS.map((entry) => ({
      value: entry.id,
      label: entry.label,
      hint: entry.envVar,
    })),
    initialValue: API_KEY_PROVIDERS[0].id,
  });
  if (cancelled(provider)) {
    outro("Setup cancelled.");
    writeResult(resultPath, { status: "cancelled" });
    return;
  }

  const spec = API_KEY_PROVIDERS.find((entry) => entry.id === provider);
  const apiKey = await text({
    message: "API key or env var",
    placeholder: spec.envVar,
    initialValue: spec.envVar,
  });
  if (cancelled(apiKey)) {
    outro("Setup cancelled.");
    writeResult(resultPath, { status: "cancelled" });
    return;
  }

  const model = await text({
    message: "Model",
    placeholder: spec.defaultModel,
    initialValue: spec.defaultModel,
  });
  if (cancelled(model)) {
    outro("Setup cancelled.");
    writeResult(resultPath, { status: "cancelled" });
    return;
  }

  writeResult(resultPath, {
    status: "ok",
    method: "api-key",
    provider,
    api_key: String(apiKey || spec.envVar).trim(),
    model: String(model || spec.defaultModel).trim(),
  });
}

main().catch((error) => {
  const options = parseArgs(process.argv.slice(2));
  writeResult(options["result-path"], {
    status: "error",
    message: error instanceof Error ? error.message : String(error),
  });
  process.exitCode = 1;
});
