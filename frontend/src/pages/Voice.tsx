import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPostAudio, apiPostForm } from "../services/api";
import type { TranscribeResponse, VoiceConfig, VoiceState } from "../types/voice";

const MIC_ENABLED_KEY = "aurora.voice.micEnabled";
const MODE_KEY = "aurora.voice.mode";
const MAX_RECORDING_MS = 15000;

type Mode = "push_to_talk" | "wake_word";

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as Record<string, unknown>;
  const ctor = (w.SpeechRecognition ?? w.webkitSpeechRecognition) as
    | (new () => SpeechRecognitionLike)
    | undefined;
  return ctor ?? null;
}

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "Idle",
  listening: "Listening...",
  processing: "Processing...",
  speaking: "Speaking...",
  wake_listening: `Waiting for wake word...`,
};

export function Voice() {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [micEnabled, setMicEnabled] = useState(() => localStorage.getItem(MIC_ENABLED_KEY) === "true");
  const [mode, setMode] = useState<Mode>(
    () => (localStorage.getItem(MODE_KEY) as Mode) || "push_to_talk",
  );
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState(0);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [speechRecognitionSupported] = useState(() => getSpeechRecognitionCtor() !== null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const speechDetectedRef = useRef(false);
  const recordingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const playerRef = useRef<HTMLAudioElement | null>(null);
  const stateRef = useRef<VoiceState>("idle");
  const modeRef = useRef<Mode>(mode);
  const micEnabledRef = useRef(micEnabled);

  stateRef.current = state;
  modeRef.current = mode;
  micEnabledRef.current = micEnabled;

  useEffect(() => {
    apiGet<VoiceConfig>("/api/voice/config")
      .then(setConfig)
      .catch((cause) => setConfigError(cause instanceof Error ? cause.message : "Failed to load voice config"));
  }, []);

  useEffect(() => {
    localStorage.setItem(MIC_ENABLED_KEY, String(micEnabled));
  }, [micEnabled]);

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode);
  }, [mode]);

  const stopVisualizer = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setVolume(0);
  }, []);

  const releaseMic = useCallback(() => {
    stopVisualizer();
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    analyserRef.current = null;
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (recordingTimeoutRef.current) clearTimeout(recordingTimeoutRef.current);
  }, [stopVisualizer]);

  async function ensureStream(): Promise<MediaStream> {
    if (streamRef.current) return streamRef.current;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    return stream;
  }

  function startVisualizer(stream: MediaStream) {
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    audioCtxRef.current = ctx;
    analyserRef.current = analyser;

    const data = new Uint8Array(analyser.frequencyBinCount);
    const threshold = config?.client_silence_threshold ?? 0.02;
    const silenceMs = config?.client_silence_duration_ms ?? 1500;

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (const sample of data) {
        const centered = (sample - 128) / 128;
        sumSquares += centered * centered;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      setVolume(rms);

      if (stateRef.current === "listening") {
        if (rms > threshold) {
          speechDetectedRef.current = true;
          silenceStartRef.current = null;
        } else if (speechDetectedRef.current) {
          if (silenceStartRef.current === null) silenceStartRef.current = performance.now();
          else if (performance.now() - silenceStartRef.current > silenceMs) {
            stopRecording();
            return;
          }
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await ensureStream();
      speechDetectedRef.current = false;
      silenceStartRef.current = null;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => handleRecordingComplete(new Blob(chunksRef.current, { type: recorder.mimeType }));
      recorderRef.current = recorder;
      recorder.start();
      setState("listening");
      startVisualizer(stream);

      recordingTimeoutRef.current = setTimeout(() => {
        if (recorderRef.current?.state === "recording") stopRecording();
      }, MAX_RECORDING_MS);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not access the microphone");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);

  function stopRecording() {
    stopVisualizer();
    if (recordingTimeoutRef.current) clearTimeout(recordingTimeoutRef.current);
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }

  async function handleRecordingComplete(blob: Blob) {
    setState("processing");
    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      const transcribed = await apiPostForm<TranscribeResponse>("/api/voice/transcribe", form);

      if (!transcribed.text.trim()) {
        setError("Didn't catch any speech in that recording.");
        await afterTurn();
        return;
      }
      setTranscript(transcribed.text);

      const chatResult = await apiPost<{ conversation_id: string; message: { content: string } }>(
        "/api/chat",
        { conversation_id: conversationId, message: transcribed.text },
      );
      setConversationId(chatResult.conversation_id);
      setResponse(chatResult.message.content);
      await speak(chatResult.message.content);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Voice turn failed");
      await afterTurn();
    }
  }

  async function speak(text: string) {
    setState("speaking");
    try {
      const blob = await apiPostAudio("/api/voice/speak", { text });
      const url = URL.createObjectURL(blob);
      if (playerRef.current) {
        playerRef.current.src = url;
        await playerRef.current.play();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Speech synthesis failed");
      await afterTurn();
    }
  }

  async function afterTurn() {
    if (modeRef.current === "wake_word" && micEnabledRef.current) {
      startWakeListening();
    } else {
      setState("idle");
    }
  }

  const startWakeListening = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor || !config) return;
    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      const results = event.results;
      const lastIndex = results.length - 1;
      if (lastIndex < 0) return;
      const text = results[lastIndex][0]?.transcript ?? "";
      if (text.toLowerCase().includes(config.wake_word.toLowerCase())) {
        recognition.stop();
        startRecording();
      }
    };
    recognition.onerror = () => {
      /* transient recognition errors are common (silence timeouts); onend restarts it */
    };
    recognition.onend = () => {
      if (modeRef.current === "wake_word" && micEnabledRef.current && stateRef.current === "wake_listening") {
        recognition.start(); // browsers auto-stop continuous recognition periodically; keep it alive
      }
    };
    recognitionRef.current = recognition;
    setState("wake_listening");
    recognition.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, startRecording]);

  useEffect(() => {
    if (!micEnabled) {
      releaseMic();
      setState("idle");
      return;
    }
    if (mode === "wake_word") {
      startWakeListening();
    }
    return () => releaseMic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micEnabled, mode]);

  useEffect(() => releaseMic, [releaseMic]);

  const micBlocked = !config?.voice_enabled;

  return (
    <main className="mx-auto max-w-2xl p-8 text-slate-200">
      <h1 className="mb-1 text-2xl font-semibold text-white">Voice</h1>
      <p className="mb-6 text-sm text-slate-400">
        Push-to-talk or wake-word ("{config?.wake_word ?? "Hey Aurora"}") voice interaction.
      </p>

      {configError && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {configError}
        </div>
      )}
      {micBlocked && !configError && (
        <div className="mb-4 rounded-md border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300">
          Voice is disabled on the backend (VOICE_ENABLED=false). Enable it in .env to use this page.
        </div>
      )}

      <div className="mb-6 flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/40 p-4">
        <div>
          <div className="text-sm font-medium text-slate-200">Microphone</div>
          <div className="text-xs text-slate-500">Fully disabled until you turn this on.</div>
        </div>
        <button
          onClick={() => setMicEnabled(!micEnabled)}
          disabled={micBlocked}
          className={`rounded-md px-4 py-2 text-sm font-medium disabled:opacity-40 ${
            micEnabled ? "bg-emerald-700 hover:bg-emerald-600" : "bg-slate-800 hover:bg-slate-700"
          }`}
        >
          {micEnabled ? "Enabled" : "Disabled"}
        </button>
      </div>

      <div className="mb-6 flex gap-2">
        <button
          onClick={() => setMode("push_to_talk")}
          className={`flex-1 rounded-md px-3 py-2 text-sm ${
            mode === "push_to_talk" ? "bg-indigo-600" : "bg-slate-800 hover:bg-slate-700"
          }`}
        >
          Push to talk
        </button>
        <button
          onClick={() => setMode("wake_word")}
          disabled={!speechRecognitionSupported}
          className={`flex-1 rounded-md px-3 py-2 text-sm disabled:opacity-40 ${
            mode === "wake_word" ? "bg-indigo-600" : "bg-slate-800 hover:bg-slate-700"
          }`}
          title={
            speechRecognitionSupported
              ? "Uses this browser's built-in speech recognition to listen for the wake word"
              : "This browser does not support the Web Speech API"
          }
        >
          Wake word
        </button>
      </div>

      <div className="mb-6 flex flex-col items-center justify-center gap-4 rounded-md border border-slate-800 bg-slate-900/40 p-8">
        <div
          className="flex h-28 w-28 items-center justify-center rounded-full border-4 transition-colors"
          style={{
            borderColor:
              state === "listening"
                ? "#6366f1"
                : state === "speaking"
                  ? "#10b981"
                  : state === "wake_listening"
                    ? "#f59e0b"
                    : "#334155",
            transform: state === "listening" ? `scale(${1 + Math.min(volume, 1) * 0.3})` : "scale(1)",
          }}
        >
          <span className="text-xs uppercase tracking-wide text-slate-400">{state}</span>
        </div>
        <div className="text-sm text-slate-400">{STATE_LABEL[state]}</div>

        {mode === "push_to_talk" && (
          <button
            onMouseDown={() => micEnabled && !micBlocked && state === "idle" && startRecording()}
            onMouseUp={() => state === "listening" && stopRecording()}
            onMouseLeave={() => state === "listening" && stopRecording()}
            disabled={!micEnabled || micBlocked || (state !== "idle" && state !== "listening")}
            className="rounded-full bg-indigo-600 px-8 py-3 text-sm font-medium hover:bg-indigo-500 disabled:opacity-40"
          >
            Hold to talk
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {transcript && (
        <div className="mb-3 rounded-md border border-slate-800 bg-slate-900/40 p-3 text-sm">
          <div className="mb-1 text-xs text-slate-500">You said</div>
          {transcript}
        </div>
      )}
      {response && (
        <div className="rounded-md border border-slate-800 bg-slate-900/40 p-3 text-sm">
          <div className="mb-1 text-xs text-slate-500">Aurora replied</div>
          {response}
        </div>
      )}

      <audio ref={playerRef} onEnded={afterTurn} className="hidden" />
    </main>
  );
}
