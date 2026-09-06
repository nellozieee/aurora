export type TriggerType = "once" | "interval" | "cron";
export type ActionType = "reminder" | "chat_message";
export type AutomationStatus = "active" | "paused" | "cancelled" | "completed";
export type TaskStatus = "created" | "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export interface AutomationOut {
  id: string;
  name: string;
  trigger_type: TriggerType;
  run_at: string | null;
  interval_seconds: number | null;
  cron_expression: string | null;
  action_type: ActionType;
  action_payload: Record<string, unknown>;
  status: AutomationStatus;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskOut {
  id: string;
  automation_id: string;
  title: string;
  status: TaskStatus;
  result: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
