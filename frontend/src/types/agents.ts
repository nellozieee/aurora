export interface AgentSummary {
  name: string;
  display_name: string;
  description: string;
  allowed_tools: string[];
  max_steps: number;
  max_execution_seconds: number;
}
