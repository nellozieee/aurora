import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../services/api";
import type { RiskLevel, ToolResult, ToolSummary } from "../types/tools";

const RISK_COLOR: Record<RiskLevel, string> = {
  safe: "bg-emerald-900 text-emerald-300",
  low: "bg-sky-900 text-sky-300",
  medium: "bg-amber-900 text-amber-300",
  high: "bg-orange-900 text-orange-300",
  critical: "bg-red-900 text-red-300",
};

function exampleArgs(schema: Record<string, unknown>): string {
  const props = (schema.properties as Record<string, { type?: string }>) ?? {};
  const example: Record<string, unknown> = {};
  for (const [key, prop] of Object.entries(props)) {
    if (prop.type === "string") example[key] = "";
    else if (prop.type === "integer" || prop.type === "number") example[key] = 0;
    else if (prop.type === "boolean") example[key] = false;
    else example[key] = null;
  }
  return JSON.stringify(example, null, 2);
}

function ToolCard({ tool }: { tool: ToolSummary }) {
  const [open, setOpen] = useState(false);
  const [argsText, setArgsText] = useState(() => exampleArgs(tool.input_schema));
  const [result, setResult] = useState<ToolResult | null>(null);
  const [running, setRunning] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  async function run() {
    let parsed: unknown;
    try {
      parsed = argsText.trim() ? JSON.parse(argsText) : {};
    } catch (cause) {
      setJsonError(cause instanceof Error ? cause.message : "Invalid JSON");
      return;
    }
    setJsonError(null);
    setRunning(true);
    setResult(null);
    try {
      const res = await apiPost<ToolResult>(`/api/tools/${tool.name}/execute`, {
        arguments: parsed,
      });
      setResult(res);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded-md border border-slate-800 bg-slate-900/40">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div>
          <span className="font-mono text-sm text-slate-100">{tool.name}</span>
          <p className="mt-0.5 text-xs text-slate-400">{tool.description}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${RISK_COLOR[tool.risk_level]}`}>
            {tool.risk_level}
          </span>
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
            {tool.permission_level}
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-800 p-4">
          <div className="mb-2 text-xs text-slate-500">Arguments (JSON)</div>
          <textarea
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-slate-700 bg-slate-950 p-2 font-mono text-xs text-slate-200 outline-none focus:border-indigo-500"
          />
          {jsonError && <div className="mt-1 text-xs text-red-400">{jsonError}</div>}
          <button
            onClick={run}
            disabled={running}
            className="mt-2 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50"
          >
            {running ? "Running..." : "Run"}
          </button>

          {result && (
            <div
              className={`mt-3 rounded-md border p-3 text-xs ${
                result.success ? "border-emerald-900 bg-emerald-950/30" : "border-red-900 bg-red-950/30"
              }`}
            >
              <div className={result.success ? "text-emerald-400" : "text-red-400"}>
                {result.success ? "success" : `error: ${result.error?.code}`}
              </div>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-slate-300">
                {JSON.stringify(result.success ? result.data : result.error?.message, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Tools() {
  const [tools, setTools] = useState<ToolSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ToolSummary[]>("/api/tools")
      .then(setTools)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Failed to load tools"));
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Tools</h1>
      <p className="mb-6 text-sm text-slate-400">
        Every capability the assistant can invoke — expand a tool to try it directly.
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {tools.map((tool) => (
          <ToolCard key={tool.name} tool={tool} />
        ))}
      </div>
    </main>
  );
}
