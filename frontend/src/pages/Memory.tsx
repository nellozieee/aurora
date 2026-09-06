import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../services/api";
import type { MemoryOut, MemoryType } from "../types/memory";

const MEMORY_TYPES: MemoryType[] = ["temporary", "conversation", "useful", "persistent", "sensitive"];

const TYPE_COLOR: Record<MemoryType, string> = {
  temporary: "bg-slate-700 text-slate-300",
  conversation: "bg-sky-900 text-sky-300",
  useful: "bg-emerald-900 text-emerald-300",
  persistent: "bg-indigo-900 text-indigo-300",
  sensitive: "bg-red-900 text-red-300",
};

export function Memory() {
  const [memories, setMemories] = useState<MemoryOut[]>([]);
  const [query, setQuery] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState<MemoryType>("useful");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(q?: string) {
    setLoading(true);
    setError(null);
    try {
      const path = q ? `/api/memory?q=${encodeURIComponent(q)}` : "/api/memory";
      const data = await apiGet<MemoryOut[]>(path);
      setMemories(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load memories");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!newContent.trim()) return;
    try {
      await apiPost("/api/memory", { content: newContent, memory_type: newType });
      setNewContent("");
      load(query || undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create memory");
    }
  }

  async function handleDelete(id: string) {
    await apiDelete(`/api/memory/${id}`);
    load(query || undefined);
  }

  async function handleDeleteAll() {
    if (!window.confirm(`Delete all ${memories.length} memories? This cannot be undone.`)) return;
    await apiDelete("/api/memory");
    load();
  }

  return (
    <main className="mx-auto max-w-3xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Memory</h1>
      <p className="mb-6 text-sm text-slate-400">
        What Aurora remembers about you — inspect, search, and delete freely.
      </p>

      <div className="mb-6 rounded-md border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-2 text-sm font-medium text-slate-300">Remember something</div>
        <div className="flex gap-2">
          <input
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="e.g. I prefer concise answers"
            className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as MemoryType)}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm"
          >
            {MEMORY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button
            onClick={handleCreate}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500"
          >
            Save
          </button>
        </div>
      </div>

      <div className="mb-4 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(query || undefined)}
          placeholder="Semantic search..."
          className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button
          onClick={() => load(query || undefined)}
          className="rounded-md bg-slate-800 px-4 py-2 text-sm hover:bg-slate-700"
        >
          Search
        </button>
        {query && (
          <button
            onClick={() => {
              setQuery("");
              load();
            }}
            className="rounded-md bg-slate-800 px-4 py-2 text-sm hover:bg-slate-700"
          >
            Clear
          </button>
        )}
        <button
          onClick={handleDeleteAll}
          disabled={memories.length === 0}
          className="rounded-md bg-red-950 px-4 py-2 text-sm text-red-300 hover:bg-red-900 disabled:opacity-40"
        >
          Delete all
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && <div className="text-sm text-slate-500">Loading...</div>}

      <div className="flex flex-col gap-2">
        {memories.map((m) => (
          <div
            key={m.id}
            className="flex items-start justify-between gap-4 rounded-md border border-slate-800 bg-slate-900/40 px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-xs ${TYPE_COLOR[m.memory_type]}`}>
                  {m.memory_type}
                </span>
                {!m.embedded && (
                  <span className="rounded bg-amber-900 px-2 py-0.5 text-xs text-amber-300">
                    not searchable (embedding failed)
                  </span>
                )}
                {m.distance !== undefined && (
                  <span className="text-xs text-slate-500">distance {m.distance.toFixed(3)}</span>
                )}
              </div>
              <div className="break-words text-sm text-slate-200">{m.content}</div>
              <div className="mt-1 text-xs text-slate-500">
                {new Date(m.created_at).toLocaleString()}
                {m.source && ` · ${m.source}`}
              </div>
            </div>
            <button
              onClick={() => handleDelete(m.id)}
              className="shrink-0 text-slate-500 hover:text-red-400"
            >
              ✕
            </button>
          </div>
        ))}
        {!loading && memories.length === 0 && (
          <div className="text-sm text-slate-500">No memories yet.</div>
        )}
      </div>
    </main>
  );
}
