const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export interface Trend {
  id: number;
  topic: string;
  source: string;
  score: number;
  used: boolean;
  created_at: string;
}

export interface StoryboardShot {
  beat: "hook" | "promise" | "body" | "payoff" | "cta";
  visual: string;
  keywords: string[];
}

export interface ScriptText {
  hook: string;
  promise: string;
  body: string;
  payoff: string;
  cta: string;
  storyboard?: StoryboardShot[];
}

export interface ScriptRecord {
  id: number;
  topic: string;
  script: ScriptText;
  style: string;
  length_variant: string;
  status: string;
  created_at: string;
}

export interface ReviewVideo {
  id: number;
  status: string;
  file_path: string | null;
  thumbnail_path: string | null;
  script: { id: number; topic: string; style: string; length_variant: string; text: ScriptRecord["script"] };
  created_at: string;
}

export const api = {
  pipelineStatus: () => request<{ stages: any[] }>("/pipeline/status"),
  pipelineEvents: (after: number) =>
    request<{ events: { id: number; stage: string; status: string; detail: string; at: string }[] }>(
      `/pipeline/events?after=${after}`
    ),
  triggerTrends: () => request<{ triggered: string }>("/pipeline/trigger/trends", { method: "POST" }),
  triggerScript: (topic: string, style = "explainer", length_variant = "30s") =>
    request<{ triggered: string }>(
      `/pipeline/trigger/script?topic=${encodeURIComponent(topic)}&style=${style}&length_variant=${length_variant}`,
      { method: "POST" }
    ),

  listTrends: () => request<Trend[]>("/trends"),

  listScripts: (topic?: string) => request<ScriptRecord[]>(`/scripts${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`),

  listPendingVideos: () => request<ReviewVideo[]>("/videos?status=pending"),
  approveVideo: (id: number) => request(`/videos/${id}/approve`, { method: "POST" }),
  rejectVideo: (id: number, note?: string) =>
    request(`/videos/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) }),
  // The rewrite/reassembly runs as a background job on the server, so
  // this only confirms the job was queued — new_script_id/new_video_id
  // aren't known yet at response time.
  regenerateVideo: (id: number, target: "script" | "video", note: string) =>
    request<{ regenerating: string; status: string; video_id: number }>(
      `/videos/${id}/regenerate`,
      { method: "POST", body: JSON.stringify({ target, note }) }
    ),

  publishHistory: () => request<any[]>("/publish/history"),

  performance: () => request<any[]>("/analytics/performance"),
  bestPerformers: () => request<{ by_style: any[]; by_topic: any[] }>("/analytics/best-performers"),

  settingsStatus: () =>
    request<{
      trend_seed_keywords: string[];
      reddit_subreddits: string[];
      voice_profile: string;
      script_provider: string;
      script_model: string;
      credentials_configured: Record<string, boolean>;
    }>("/settings"),
};
