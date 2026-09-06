export type RiskLevel = "safe" | "low" | "medium" | "high" | "critical";
export type PermissionLevel = "safe" | "user" | "confirm";

export interface ToolSummary {
  name: string;
  description: string;
  risk_level: RiskLevel;
  permission_level: PermissionLevel;
  timeout_seconds: number;
  input_schema: Record<string, unknown>;
}

export interface ToolError {
  code: string;
  message: string;
}

export interface ToolResult {
  success: boolean;
  data: unknown;
  error: ToolError | null;
  metadata: Record<string, unknown>;
}
