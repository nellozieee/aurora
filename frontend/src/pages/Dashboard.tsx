import { useEffect, useState } from "react";
import { ApiError, apiGet } from "../services/api";
import type { SubsystemStatus, SystemStatus } from "../types/system";

const STATUS_COLOR: Record<SubsystemStatus, string> = {
  online: "bg-emerald-500",
  offline: "bg-slate-500",
  degraded: "bg-amber-500",
  not_configured: "bg-slate-600",
  error: "bg-red-500",
};

function StatusDot({ status }: { status: SubsystemStatus }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_COLOR[status]}`} />;
}

export function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await apiGet<SystemStatus>("/api/system/status");
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : "Unknown error");
        }
      }
    }

    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <main className="min-h-screen bg-[#0b0e14] p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">
        {status?.assistant_name ?? "Aurora"}
      </h1>
      <p className="mb-6 text-sm text-slate-400">Personal AI assistant — system dashboard</p>

      {error && (
        <div className="mb-6 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          Could not reach backend: {error}
        </div>
      )}

      {status && (
        <div className="grid max-w-md gap-3">
          {Object.entries(status.subsystems).map(([name, value]) => (
            <div
              key={name}
              className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/60 px-4 py-3"
            >
              <span className="capitalize text-slate-300">{name}</span>
              <span className="flex items-center gap-2 text-sm text-slate-400">
                <StatusDot status={value} />
                {value}
              </span>
            </div>
          ))}
          <div className="mt-2 text-xs text-slate-500">
            Uptime: {Math.floor(status.uptime_seconds)}s · Environment: {status.environment}
          </div>
        </div>
      )}
    </main>
  );
}
