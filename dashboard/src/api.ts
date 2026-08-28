const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  if (res.status === 401 && path !== "/auth/status" && path !== "/auth/login") {
    // The session expired (cookie aged out, or the backend restarted and
    // lost its in-memory fallback secret) mid-visit - force a full reload
    // so App re-checks /auth/status and lands back on the login screen,
    // instead of every page's data silently failing to load.
    window.location.href = "/";
  }
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
  scheduled_for: string | null;
  script: { id: number; topic: string; style: string; length_variant: string; text: ScriptRecord["script"] };
  created_at: string;
}

export interface PostingSlot {
  id: number;
  label: string;
  days_of_week: number[];
  time_of_day: string;
  platforms: string[] | null;
  enabled: boolean;
  last_fired_date: string | null;
  created_at: string;
}

export interface BestPostingTime {
  hour: number;
  avg_views: number;
  sample_count: number;
}

export interface PerformanceRow {
  id: number;
  video_id: number;
  topic: string;
  platform: string;
  views: number;
  retention_pct: number;
  completion_pct: number;
  likes: number;
  shares: number;
  pulled_at: string;
}

export interface AutomationStatus {
  auto_generate_enabled: boolean;
  auto_trend_finder_enabled: boolean;
  auto_approve_enabled: boolean;
  ab_test_enabled: boolean;
  digest_enabled: boolean;
  cleanup_enabled: boolean;
  daily_cost_budget_usd: number;
  monthly_cost_budget_usd: number;
}

export interface SpendSummary {
  daily_spend_usd: number;
  daily_budget_usd: number;
  monthly_spend_usd: number;
  monthly_budget_usd: number;
  total_calls: number;
  by_day: { date: string; cost_usd: number }[];
  by_provider: { provider: string; cost_usd: number }[];
}

export const api = {
  authStatus: () => request<{ enabled: boolean; authenticated: boolean }>("/auth/status"),
  login: (password: string) =>
    request<{ authenticated: boolean }>("/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request<{ authenticated: boolean }>("/auth/logout", { method: "POST" }),

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
  // Approved videos whose scheduled_for is more than 15 minutes overdue
  // - the scheduler retries a failed publish forever, silently, so this
  // is the only place a stuck one becomes visible.
  needsAttention: () => request<ReviewVideo[]>("/videos/needs-attention"),
  // Text-only fix (hook/promise/body/payoff/cta) - does NOT re-render
  // the video; pair with "Regenerate video" to bake the change into a
  // fresh render without spending an LLM call on a full script rewrite.
  editScript: (id: number, fields: Partial<{ hook: string; promise: string; body: string; payoff: string; cta: string }>) =>
    request<ReviewVideo>(`/videos/${id}/script`, { method: "PATCH", body: JSON.stringify(fields) }),
  // scheduledFor: an ISO datetime string in the future — publish_video()
  // then just stores it and returns instead of publishing immediately;
  // the scheduler loop (started from main.py's lifespan) picks it up
  // once that time arrives.
  approveVideo: (id: number, scheduledFor?: string) =>
    request(`/videos/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ scheduled_for: scheduledFor || null }),
    }),
  rejectVideo: (id: number, note?: string) =>
    request(`/videos/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) }),
  listScheduled: () => request<ReviewVideo[]>("/videos/scheduled/upcoming"),
  // Spreads video_ids across start_at, start_at + interval_hours, + 2*interval_hours, ...
  // — only videos still "pending" are picked up, per the endpoint's own doc.
  batchSchedule: (videoIds: number[], startAt: string, intervalHours: number) =>
    request<{ scheduled: { video_id: number; scheduled_for: string }[] }>("/videos/batch-schedule", {
      method: "POST",
      body: JSON.stringify({ video_ids: videoIds, start_at: startAt, interval_hours: intervalHours }),
    }),
  unscheduleVideo: (id: number) => request<ReviewVideo>(`/videos/${id}/unschedule`, { method: "POST" }),
  // The rewrite/reassembly runs as a background job on the server, so
  // this only confirms the job was queued — new_script_id/new_video_id
  // aren't known yet at response time.
  regenerateVideo: (id: number, target: "script" | "video", note: string) =>
    request<{ regenerating: string; status: string; video_id: number }>(
      `/videos/${id}/regenerate`,
      { method: "POST", body: JSON.stringify({ target, note }) }
    ),

  publishHistory: () => request<any[]>("/publish/history"),

  performance: () => request<PerformanceRow[]>("/analytics/performance"),
  bestPerformers: () => request<{ by_style: any[]; by_topic: any[] }>("/analytics/best-performers"),
  bestPostingTimes: () => request<Record<string, BestPostingTime[]>>("/analytics/best-times"),

  spendSummary: () => request<SpendSummary>("/automation/spend"),

  listSlots: () => request<PostingSlot[]>("/publish/slots"),
  createSlot: (slot: { label: string; days_of_week: number[]; time_of_day: string; platforms: string[] | null }) =>
    request<PostingSlot>("/publish/slots", { method: "POST", body: JSON.stringify(slot) }),
  updateSlot: (
    id: number,
    patch: Partial<{ label: string; days_of_week: number[]; time_of_day: string; platforms: string[] | null; enabled: boolean }>
  ) => request<PostingSlot>(`/publish/slots/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSlot: (id: number) => request(`/publish/slots/${id}`, { method: "DELETE" }),

  accountsStatus: () =>
    request<{
      youtube: { configured: boolean; connected: boolean };
      tiktok: { configured: boolean; connected: boolean };
      instagram: { configured: boolean; connected: boolean };
    }>("/publish/accounts/status"),
  disconnectYouTube: () => request("/publish/accounts/youtube/disconnect", { method: "POST" }),
  disconnectTikTok: () => request("/publish/accounts/tiktok/disconnect", { method: "POST" }),
  disconnectInstagram: () => request("/publish/accounts/instagram/disconnect", { method: "POST" }),

  settingsStatus: () =>
    request<{
      trend_seed_keywords: string[];
      reddit_subreddits: string[];
      voice_profile: string;
      script_provider: string;
      script_model: string;
      credentials_configured: Record<string, boolean>;
      automation: AutomationStatus;
    }>("/settings"),
  // Every *_enabled flag here is live: main.py's automation loops
  // re-check their own setting every minute, so this takes effect
  // without a restart. The budget numbers aren't settable here.
  updateAutomation: (
    patch: Partial<{
      auto_generate_enabled: boolean;
      auto_trend_finder_enabled: boolean;
      auto_approve_enabled: boolean;
      ab_test_enabled: boolean;
      digest_enabled: boolean;
      cleanup_enabled: boolean;
    }>
  ) => request<AutomationStatus>("/settings/automation", { method: "PATCH", body: JSON.stringify(patch) }),
};
