/**
 * V2 API client — match listing, extraction, auth.
 */

const BASE = import.meta.env.VITE_API_BASE || "";

function getToken(): string | null {
  return localStorage.getItem("fps_token");
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleResponse(res: Response) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.message || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function signup(email: string, password: string) {
  const res = await fetch(`${BASE}/api/v2/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

export async function login(email: string, password: string) {
  const res = await fetch(`${BASE}/api/v2/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

// ── Matches ──────────────────────────────────────────────────────────────────

export interface MatchItem {
  id: number;
  espn_match_id: string;
  match_number: number | null;
  title: string | null;
  team1: string | null;
  team2: string | null;
  venue: string | null;
  match_date: string | null;
  status: string;
  result_text: string | null;
  scorecard_url: string | null;
  extracted_at: string | null;
}

export interface MatchListResponse {
  matches: MatchItem[];
  total: number;
}

export async function fetchMatches(
  status?: string,
  limit = 100,
  offset = 0
): Promise<MatchListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const res = await fetch(`${BASE}/api/v2/matches?${params}`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

// ── Extraction (SSE) ─────────────────────────────────────────────────────────

export function extractMatchStream(
  matchId: number,
  onProgress: (step: string, message: string) => void,
  onDone: (data: any) => void,
  onError: (message: string) => void
): () => void {
  const url = `${BASE}/api/v2/matches/${matchId}/extract-stream`;
  const es = new EventSource(url);

  es.addEventListener("progress", (e) => {
    const d = JSON.parse(e.data);
    onProgress(d.step, d.message);
  });

  es.addEventListener("done", (e) => {
    const d = JSON.parse(e.data);
    onDone(d);
    es.close();
  });

  es.addEventListener("error", (e: any) => {
    if (e.data) {
      const d = JSON.parse(e.data);
      onError(d.message);
    } else {
      onError("Connection lost");
    }
    es.close();
  });

  es.onerror = () => {
    onError("Connection lost");
    es.close();
  };

  // Return cleanup function
  return () => es.close();
}

// ── Points & Sheet ───────────────────────────────────────────────────────────

export async function fetchMatchPoints(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/points`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function calculatePointsV2(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/calculate`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
  });
  return handleResponse(res);
}

export async function updateSheetV2(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/update-sheet`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
  });
  return handleResponse(res);
}

export async function editPlayersV2(
  matchId: number,
  edits: { original_name: string; new_name?: string; new_total_points?: number }[]
) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/edit-players`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ match_id: String(matchId), edits }),
  });
  return handleResponse(res);
}

// ── Scheduler ────────────────────────────────────────────────────────────────

export async function triggerDiscovery() {
  const res = await fetch(`${BASE}/api/v2/scheduler/run`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function getSchedulerStatus() {
  const res = await fetch(`${BASE}/api/v2/scheduler/status`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}
