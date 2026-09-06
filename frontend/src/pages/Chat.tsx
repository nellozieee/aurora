import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { apiDelete, apiGet, openChatSocket } from "../services/api";
import type { ChatMessageOut, ChatWsEvent, ConversationDetail, ConversationSummary } from "../types/chat";

interface ActivityItem {
  id: string;
  label: string;
  status: "running" | "done" | "failed";
}

interface DisplayMessage {
  id: string;
  role: ChatMessageOut["role"];
  content: string;
  pending?: boolean;
  activity?: ActivityItem[];
  imagePreview?: string;
}

function ActivityTrail({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-1.5 flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item.id}
          className={`rounded px-2 py-0.5 text-xs ${
            item.status === "running"
              ? "bg-slate-700 text-slate-300"
              : item.status === "failed"
                ? "bg-red-950 text-red-300"
                : "bg-slate-800 text-slate-400"
          }`}
        >
          {item.status === "running" && "⏳ "}
          {item.status === "done" && "✓ "}
          {item.status === "failed" && "✕ "}
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function Chat() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingIntentRef = useRef<string | null>(null);

  async function refreshConversations() {
    try {
      const list = await apiGet<ConversationSummary[]>("/api/conversations");
      setConversations(list);
    } catch {
      // dashboard-level status already reports backend/db issues; keep chat quiet here
    }
  }

  useEffect(() => {
    refreshConversations();
  }, []);

  function ensurePendingAssistant(prev: DisplayMessage[]): DisplayMessage[] {
    const next = [...prev];
    const last = next[next.length - 1];
    if (!last?.pending) {
      next.push({ id: "pending", role: "assistant", content: "", pending: true, activity: [] });
    }
    return next;
  }

  function pushActivity(label: string, status: ActivityItem["status"] = "running") {
    setMessages((prev) => {
      const next = ensurePendingAssistant(prev);
      const last = next[next.length - 1];
      last.activity = [...(last.activity ?? []), { id: `${Date.now()}-${Math.random()}`, label, status }];
      return next;
    });
  }

  function updateLastActivity(matchLabelPrefix: string, newLabel: string, status: ActivityItem["status"]) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (!last?.activity) return next;
      const idx = [...last.activity].reverse().findIndex((a) => a.label.startsWith(matchLabelPrefix));
      if (idx === -1) return next;
      const realIdx = last.activity.length - 1 - idx;
      last.activity = [...last.activity];
      last.activity[realIdx] = { ...last.activity[realIdx], label: newLabel, status };
      return next;
    });
  }

  useEffect(() => {
    const socket = openChatSocket();
    socketRef.current = socket;
    let closedByCleanup = false;

    socket.onopen = () => {
      setConnected(true);
      setError(null);
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => {
      if (!closedByCleanup) setError("WebSocket connection error");
    };

    socket.onmessage = (event) => {
      const data: ChatWsEvent = JSON.parse(event.data);

      switch (data.type) {
        case "conversation_started":
          setConversationId(data.conversation_id);
          break;
        case "intent_classified":
          pendingIntentRef.current = data.intent;
          break;
        case "agent_selected":
          pushActivity(
            `${data.agent} agent${pendingIntentRef.current ? ` (${pendingIntentRef.current})` : ""}`,
            "done",
          );
          pendingIntentRef.current = null;
          break;
        case "tool_started":
          pushActivity(`${data.tool}(${Object.values(data.arguments).join(", ")})`, "running");
          break;
        case "tool_completed":
          updateLastActivity(data.tool, `${data.tool}`, data.success ? "done" : "failed");
          break;
        case "plan_created":
          pushActivity(`plan: ${data.steps.length} steps`, "done");
          break;
        case "step_started":
          pushActivity(`step ${data.step_id}: ${data.description}`, "running");
          break;
        case "step_completed":
          updateLastActivity(`step ${data.step_id}`, `step ${data.step_id} done`, "done");
          break;
        case "review":
          pushActivity(data.approved ? "review: approved" : `review: ${data.notes}`, data.approved ? "done" : "failed");
          break;
        case "agent_error":
          pushActivity(`error: ${data.message}`, "failed");
          setError(data.message);
          setSending(false);
          break;
        case "assistant_message_delta":
          setMessages((prev) => {
            const next = ensurePendingAssistant(prev);
            const last = next[next.length - 1];
            last.content += data.content;
            return next;
          });
          break;
        case "assistant_message":
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.pending) {
              last.id = data.message_id;
              last.content = data.content;
              last.pending = false;
            }
            return next;
          });
          setSending(false);
          refreshConversations();
          break;
        case "error":
          setError(data.message);
          setSending(false);
          break;
      }
    };

    return () => {
      closedByCleanup = true;
      socket.close();
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadConversation(id: string) {
    const detail = await apiGet<ConversationDetail>(`/api/conversations/${id}`);
    setConversationId(detail.id);
    setMessages(detail.messages.map((m) => ({ id: m.id, role: m.role, content: m.content })));
  }

  function startNewConversation() {
    setConversationId(null);
    setMessages([]);
    setError(null);
  }

  async function removeConversation(id: string) {
    await apiDelete(`/api/conversations/${id}`);
    if (id === conversationId) startNewConversation();
    refreshConversations();
  }

  function send() {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || !input.trim()) return;

    setError(null);
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content: input, imagePreview: attachedImage ?? undefined },
    ]);
    socket.send(
      JSON.stringify({
        conversation_id: conversationId,
        message: input,
        image_base64: attachedImage,
      }),
    );
    setInput("");
    setAttachedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setAttachedImage(reader.result as string);
    reader.readAsDataURL(file);
  }

  return (
    <div className="flex h-screen bg-[#0b0e14] text-slate-200">
      <aside className="w-64 shrink-0 border-r border-slate-800 p-4">
        <button
          onClick={startNewConversation}
          className="mb-4 w-full rounded-md bg-slate-800 px-3 py-2 text-sm hover:bg-slate-700"
        >
          + New conversation
        </button>
        <div className="flex flex-col gap-1">
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`group flex items-center justify-between rounded-md px-3 py-2 text-sm hover:bg-slate-800 ${
                c.id === conversationId ? "bg-slate-800" : ""
              }`}
            >
              <button onClick={() => loadConversation(c.id)} className="flex-1 truncate text-left">
                {c.title || "Untitled"}
              </button>
              <button
                onClick={() => removeConversation(c.id)}
                className="ml-2 hidden text-slate-500 hover:text-red-400 group-hover:inline"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="border-b border-slate-800 px-6 py-3 text-sm text-slate-400">
          Aurora Chat — {connected ? "connected" : "disconnected"}
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.map((m) => (
            <div key={m.id} className={`mb-4 flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-2xl ${m.role === "user" ? "" : "w-full"}`}>
                {m.role === "assistant" && m.activity && <ActivityTrail items={m.activity} />}
                <div
                  className={`whitespace-pre-wrap rounded-lg px-4 py-2 text-sm ${
                    m.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-100"
                  }`}
                >
                  {m.imagePreview && (
                    <img src={m.imagePreview} alt="attachment" className="mb-2 max-h-48 rounded-md" />
                  )}
                  {m.content}
                  {m.pending && <span className="animate-pulse">▍</span>}
                </div>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="border-t border-red-900 bg-red-950/40 px-6 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="border-t border-slate-800 p-4">
          {attachedImage && (
            <div className="mb-2 flex items-center gap-2">
              <img src={attachedImage} alt="attachment preview" className="h-16 rounded-md border border-slate-700" />
              <button
                onClick={() => {
                  setAttachedImage(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="text-xs text-slate-500 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          )}
          <div className="flex gap-2">
            <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" id="chat-image-input" />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={sending}
              title="Attach an image"
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-50"
            >
              📎
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={sending}
              placeholder="Message Aurora..."
              className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm outline-none focus:border-indigo-500 disabled:opacity-50"
            />
            <button
              onClick={send}
              disabled={sending || !connected}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
