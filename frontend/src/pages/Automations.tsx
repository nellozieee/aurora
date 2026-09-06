import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "../services/api";
import type { ActionType, AutomationOut, TriggerType } from "../types/automation";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-emerald-900 text-emerald-300",
  paused: "bg-amber-900 text-amber-300",
  cancelled: "bg-slate-700 text-slate-400",
  completed: "bg-sky-900 text-sky-300",
};

export function Automations() {
  const [automations, setAutomations] = useState<AutomationOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<TriggerType>("once");
  const [runAt, setRunAt] = useState("");
  const [intervalSeconds, setIntervalSeconds] = useState(3600);
  const [cronExpression, setCronExpression] = useState("0 8 * * 1");
  const [actionType, setActionType] = useState<ActionType>("reminder");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const data = await apiGet<AutomationOut[]>("/api/automations");
      setAutomations(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load automations");
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleCreate() {
    if (!name.trim() || !message.trim()) return;
    setError(null);
    try {
      await apiPost("/api/automations", {
        name,
        trigger_type: triggerType,
        run_at: triggerType === "once" ? runAt : undefined,
        interval_seconds: triggerType === "interval" ? intervalSeconds : undefined,
        cron_expression: triggerType === "cron" ? cronExpression : undefined,
        action_type: actionType,
        action_payload: { message },
      });
      setName("");
      setMessage("");
      setRunAt("");
      load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create automation");
    }
  }

  async function patchStatus(id: string, status: string) {
    await apiPatch(`/api/automations/${id}`, { status });
    load();
  }

  async function remove(id: string) {
    await apiDelete(`/api/automations/${id}`);
    load();
  }

  return (
    <main className="mx-auto max-w-3xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Automations</h1>
      <p className="mb-6 text-sm text-slate-400">
        Scheduled reminders and tasks. Aurora also creates these automatically from chat (e.g. "remind me in
        5 minutes").
      </p>

      <div className="mb-6 rounded-md border border-slate-800 bg-slate-900/40 p-4">
        <div className="mb-3 text-sm font-medium text-slate-300">Create automation</div>
        <div className="mb-2 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
          <select
            value={triggerType}
            onChange={(e) => setTriggerType(e.target.value as TriggerType)}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm"
          >
            <option value="once">once</option>
            <option value="interval">interval</option>
            <option value="cron">cron</option>
          </select>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value as ActionType)}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm"
          >
            <option value="reminder">reminder</option>
            <option value="chat_message">chat_message</option>
          </select>
        </div>
        <div className="mb-2 flex gap-2">
          {triggerType === "once" && (
            <input
              type="datetime-local"
              value={runAt}
              onChange={(e) => setRunAt(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          )}
          {triggerType === "interval" && (
            <input
              type="number"
              value={intervalSeconds}
              onChange={(e) => setIntervalSeconds(Number(e.target.value))}
              placeholder="interval seconds"
              className="w-40 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          )}
          {triggerType === "cron" && (
            <input
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              placeholder="cron expression"
              className="w-48 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          )}
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={actionType === "reminder" ? "Reminder message" : "Message to send to Aurora"}
            className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <button onClick={handleCreate} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500">
          Create
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {automations.map((a) => (
          <div key={a.id} className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-medium text-slate-100">{a.name}</span>
              <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[a.status] ?? ""}`}>{a.status}</span>
            </div>
            <div className="mb-2 text-xs text-slate-500">
              {a.trigger_type} · {a.action_type}
              {a.next_run_at && ` · next: ${new Date(a.next_run_at + "Z").toLocaleString()}`}
              {a.last_run_at && ` · last: ${new Date(a.last_run_at + "Z").toLocaleString()}`}
            </div>
            <div className="flex gap-2">
              {a.status === "active" && (
                <button onClick={() => patchStatus(a.id, "paused")} className="text-xs text-slate-400 hover:text-white">
                  Pause
                </button>
              )}
              {a.status === "paused" && (
                <button onClick={() => patchStatus(a.id, "active")} className="text-xs text-slate-400 hover:text-white">
                  Resume
                </button>
              )}
              {(a.status === "active" || a.status === "paused") && (
                <button onClick={() => patchStatus(a.id, "cancelled")} className="text-xs text-slate-400 hover:text-red-400">
                  Cancel
                </button>
              )}
              <button onClick={() => remove(a.id)} className="text-xs text-slate-500 hover:text-red-400">
                Delete
              </button>
            </div>
          </div>
        ))}
        {automations.length === 0 && <div className="text-sm text-slate-500">No automations yet.</div>}
      </div>
    </main>
  );
}
