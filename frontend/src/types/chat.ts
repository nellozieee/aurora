export type MessageRole = "system" | "user" | "assistant" | "tool" | "error";

export interface ChatMessageOut {
  id: string;
  role: MessageRole;
  content: string;
  provider: string | null;
  model: string | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessageOut[];
}

export interface ToolResultOut {
  success: boolean;
  data: unknown;
  error: { code: string; message: string } | null;
  metadata: Record<string, unknown>;
}

export type ChatWsEvent =
  | { type: "conversation_started"; conversation_id: string }
  | { type: "assistant_message_delta"; content: string }
  | { type: "assistant_message"; conversation_id: string; message_id: string; content: string; provider: string }
  | { type: "error"; message: string }
  | { type: "intent_classified"; intent: string }
  | { type: "agent_selected"; agent: string }
  | { type: "tool_started"; tool: string; arguments: Record<string, unknown> }
  | { type: "tool_completed"; tool: string; success: boolean; result: ToolResultOut }
  | { type: "plan_created"; goal: string; steps: string[] }
  | { type: "step_started"; step_id: number; description: string }
  | { type: "step_completed"; step_id: number; result: string }
  | { type: "review"; approved: boolean; notes: string }
  | { type: "agent_error"; code: string; message: string };
