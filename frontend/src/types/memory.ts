export type MemoryType = "temporary" | "conversation" | "useful" | "persistent" | "sensitive";

export interface MemoryOut {
  id: string;
  content: string;
  memory_type: MemoryType;
  source: string | null;
  metadata: Record<string, unknown>;
  embedded: boolean;
  created_at: string;
  updated_at: string;
  distance?: number;
}
