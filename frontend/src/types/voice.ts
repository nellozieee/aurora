export interface VoiceConfig {
  voice_enabled: boolean;
  voice_mode: "disabled" | "push_to_talk" | "wake_word";
  wake_word: string;
  stt_provider: string;
  tts_provider: string;
  client_silence_threshold: number;
  client_silence_duration_ms: number;
}

export interface TranscribeResponse {
  text: string;
  provider: string;
  model: string;
  language: string | null;
}

export type VoiceState = "idle" | "listening" | "processing" | "speaking" | "wake_listening";
