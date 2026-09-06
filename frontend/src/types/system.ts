export type SubsystemStatus = "online" | "offline" | "degraded" | "not_configured" | "error";

export interface SystemStatus {
  assistant_name: string;
  environment: string;
  uptime_seconds: number;
  subsystems: Record<string, SubsystemStatus>;
}
