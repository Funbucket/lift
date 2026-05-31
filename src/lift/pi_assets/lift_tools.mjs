import { execFile } from "node:child_process";

const LIFT_BIN = process.env.LIFT_BIN || "lift";

function stringParam(description) {
  return { type: "string", description };
}

function numberParam(description) {
  return { type: "number", description };
}

function booleanParam(description) {
  return { type: "boolean", description };
}

function objectSchema(properties, required = []) {
  return {
    type: "object",
    properties,
    required,
    additionalProperties: false,
  };
}

function runLift(args) {
  return new Promise((resolve) => {
    execFile(LIFT_BIN, args, {
      env: process.env,
      timeout: 10 * 60 * 1000,
      maxBuffer: 20 * 1024 * 1024,
    }, (error, stdout, stderr) => {
      if (error) {
        resolve({
          ok: false,
          command: [LIFT_BIN, ...args].join(" "),
          error: error.message,
          stderr,
          stdout,
        });
        return;
      }
      resolve({
        ok: true,
        command: [LIFT_BIN, ...args].join(" "),
        stdout,
        stderr,
      });
    });
  });
}

function jsonOrText(result) {
  if (!result.ok) return JSON.stringify(result, null, 2);
  const text = result.stdout.trim();
  if (!text) return JSON.stringify(result, null, 2);
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function content(text) {
  return {
    content: [{ type: "text", text }],
    details: {},
  };
}

function addOptional(args, flag, value) {
  if (value === undefined || value === null || value === "") return;
  args.push(flag, String(value));
}

export default function (pi) {
  pi.registerTool({
    name: "lift_inspect_dataset",
    label: "Lift Inspect Dataset",
    description: "Infer schema and validate a treatment/control campaign CSV before causal analysis.",
    parameters: objectSchema({
      dataset: stringParam("Path to the campaign CSV dataset."),
    }, ["dataset"]),
    async execute(_toolCallId, params) {
      const result = await runLift(["inspect", params.dataset]);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_analyze_campaign",
    label: "Lift Analyze Campaign",
    description: "Estimate campaign incrementality, train Lift models, create curves, targets, simulation, and report artifacts.",
    parameters: objectSchema({
      dataset: stringParam("Path to the campaign CSV dataset."),
      budget: numberParam("Optional campaign budget constraint."),
      min_roi: numberParam("Optional minimum incremental ROI constraint."),
      estimate_propensity: booleanParam("Estimate treatment propensity for observational data."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["dataset"]),
    async execute(_toolCallId, params) {
      const args = ["analyze", params.dataset];
      addOptional(args, "--budget", params.budget);
      addOptional(args, "--min-roi", params.min_roi);
      addOptional(args, "--output-root", params.output_root);
      if (params.estimate_propensity) args.push("--estimate-propensity");
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_simulate_policy",
    label: "Lift Simulate Policy",
    description: "Run budget-constrained and/or ROI-constrained targeting for a completed Lift run.",
    parameters: objectSchema({
      run_id: stringParam("Lift run id returned by lift_analyze_campaign or listed by lift_outputs."),
      budget: numberParam("Optional campaign budget constraint."),
      min_roi: numberParam("Optional minimum incremental ROI constraint."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["run_id"]),
    async execute(_toolCallId, params) {
      const args = ["simulate", params.run_id];
      addOptional(args, "--budget", params.budget);
      addOptional(args, "--min-roi", params.min_roi);
      addOptional(args, "--output-root", params.output_root);
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_export_targets",
    label: "Lift Export Targets",
    description: "Write or refresh targets.csv for a completed Lift run under budget and ROI constraints.",
    parameters: objectSchema({
      run_id: stringParam("Lift run id."),
      budget: numberParam("Optional campaign budget constraint."),
      min_roi: numberParam("Optional minimum incremental ROI constraint."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["run_id"]),
    async execute(_toolCallId, params) {
      const args = ["export-targets", params.run_id];
      addOptional(args, "--budget", params.budget);
      addOptional(args, "--min-roi", params.min_roi);
      addOptional(args, "--output-root", params.output_root);
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_report",
    label: "Lift Report",
    description: "Open or refresh the Markdown report for a completed Lift run.",
    parameters: objectSchema({
      run_id: stringParam("Lift run id."),
      refresh: booleanParam("Refresh report.md from current artifacts before returning it."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["run_id"]),
    async execute(_toolCallId, params) {
      const args = ["report", params.run_id];
      addOptional(args, "--output-root", params.output_root);
      if (params.refresh) args.push("--refresh");
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_outputs",
    label: "Lift Outputs",
    description: "List previous Lift runs and summaries.",
    parameters: objectSchema({
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }),
    async execute(_toolCallId, params) {
      const args = ["outputs"];
      addOptional(args, "--output-root", params.output_root);
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_compare_models",
    label: "Lift Compare Models",
    description: "Compare model evaluation metrics (AUUC, AUCC, Qini, gain-at-budget) across all models for a completed Lift run. Use this to answer which model performs best.",
    parameters: objectSchema({
      run_id: stringParam("Lift run id returned by lift_analyze_campaign or listed by lift_outputs."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["run_id"]),
    async execute(_toolCallId, params) {
      const args = ["compare-models", params.run_id];
      addOptional(args, "--output-root", params.output_root);
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerTool({
    name: "lift_budget_frontier",
    label: "Lift Budget Frontier",
    description: "Return the budget-gain frontier curve for a completed Lift run. Shows how incremental gain changes as budget increases. Use this to answer 'how much gain do we get at budget X?' or 'what budget do we need for Y gain?'",
    parameters: objectSchema({
      run_id: stringParam("Lift run id returned by lift_analyze_campaign or listed by lift_outputs."),
      output_root: stringParam("Optional output directory. Defaults to ~/.lift/outputs."),
    }, ["run_id"]),
    async execute(_toolCallId, params) {
      const args = ["budget-frontier", params.run_id];
      addOptional(args, "--output-root", params.output_root);
      const result = await runLift(args);
      return content(jsonOrText(result));
    },
  });

  pi.registerCommand("lift-help", {
    description: "Show Lift analysis capabilities and required dataset columns.",
    handler: async (_args, ctx) => {
      ctx.ui.notify("Ask a natural-language campaign question, or provide a CSV path and ask Lift to analyze it.", "info");
    },
  });
}
