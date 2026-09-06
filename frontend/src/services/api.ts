const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handle<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : "";
    } catch {
      // response had no JSON body
    }
    throw new ApiError(`Request to ${path} failed${detail}`, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`);
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  return handle<T>(response, path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  return handle<T>(response, path);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  return handle<T>(response, path);
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method: "POST", body: form });
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  return handle<T>(response, path);
}

export async function apiPostAudio(path: string, body: unknown): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  if (!response.ok) {
    let detail = "";
    try {
      const parsed = await response.json();
      detail = parsed?.detail ? `: ${parsed.detail}` : "";
    } catch {
      // no JSON body
    }
    throw new ApiError(`Request to ${path} failed${detail}`, response.status);
  }
  return await response.blob();
}

export async function apiDelete(path: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  } catch (cause) {
    throw new ApiError(`Network error while reaching backend: ${(cause as Error).message}`);
  }
  await handle<void>(response, path);
}

export function openChatSocket(): WebSocket {
  return new WebSocket(`${WS_BASE_URL}/api/chat/ws`);
}
