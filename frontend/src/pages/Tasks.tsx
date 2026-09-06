import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../services/api";
import type { TaskOut } from "../types/automation";

const STATUS_COLOR: Record<string, string> = {
  created: "bg-slate-700 text-slate-300",
  queued: "bg-slate-700 text-slate-300",
  running: "bg-sky-900 text-sky-300",
  paused: "bg-amber-900 text-amber-300",
  completed: "bg-emerald-900 text-emerald-300",
  failed: "bg-red-900 text-red-300",
  cancelled: "bg-slate-700 text-slate-400",
};

export function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiGet<TaskOut[]>("/api/tasks");
      setTasks(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load tasks");
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function retry(id: string) {
    await apiPost(`/api/tasks/${id}/retry`, {});
    load();
  }

  async function remove(id: string) {
    await apiDelete(`/api/tasks/${id}`);
    load();
  }

  return (
    <main className="mx-auto max-w-3xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Tasks</h1>
      <p className="mb-6 text-sm text-slate-400">
        Every time an automation fires, it shows up here as one tracked execution.
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {tasks.map((t) => (
          <div key={t.id} className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-medium text-slate-100">{t.title}</span>
              <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[t.status] ?? ""}`}>{t.status}</span>
            </div>
            {t.result && <div className="mb-1 text-sm text-slate-300">{t.result}</div>}
            {t.error && <div className="mb-1 text-sm text-red-400">{t.error}</div>}
            <div className="mb-2 text-xs text-slate-500">
              created {new Date(t.created_at + "Z").toLocaleString()}
              {t.completed_at && ` · completed ${new Date(t.completed_at + "Z").toLocaleString()}`}
            </div>
            <div className="flex gap-2">
              {t.status === "failed" && (
                <button onClick={() => retry(t.id)} className="text-xs text-slate-400 hover:text-white">
                  Retry
                </button>
              )}
              {t.status !== "running" && (
                <button onClick={() => remove(t.id)} className="text-xs text-slate-500 hover:text-red-400">
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
        {tasks.length === 0 && <div className="text-sm text-slate-500">No tasks yet.</div>}
      </div>
    </main>
  );
}
