import { useEffect, useState } from "react";
import { apiGet } from "../services/api";
import type { AgentSummary } from "../types/agents";

export function Agents() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<AgentSummary[]>("/api/agents")
      .then(setAgents)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Failed to load agents"));
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Agents</h1>
      <p className="mb-6 text-sm text-slate-400">
        The orchestrator classifies each message's intent and routes it to one of these agents.
        Planning and Reviewer agents run behind the scenes for complex/research requests and
        aren't listed here since they don't call tools directly.
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3">
        {agents.map((a) => (
          <div key={a.name} className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-medium text-slate-100">{a.display_name}</span>
              <span className="text-xs text-slate-500">
                max {a.max_steps} steps · {a.max_execution_seconds}s budget
              </span>
            </div>
            <p className="mb-3 text-sm text-slate-400">{a.description}</p>
            <div className="flex flex-wrap gap-1.5">
              {a.allowed_tools.length === 0 && (
                <span className="text-xs text-slate-600">no tools</span>
              )}
              {a.allowed_tools.map((t) => (
                <span key={t} className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                  {t}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
