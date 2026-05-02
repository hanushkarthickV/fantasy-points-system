/**
 * V2 API client — match listing, queued extraction, points review, auth.
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
  last_sync_time: string | null;
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

// ── Queue-based Extraction ──────────────────────────────────────────────────

export async function queueExtraction(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/queue-extract`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
  });
  return handleResponse(res);
}

export async function fetchQueueStatus() {
  const res = await fetch(`${BASE}/api/v2/queue/status`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

// ── Points & Sheet ───────────────────────────────────────────────────────────

export async function fetchMatchPoints(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/points`, {
    headers: authHeaders(),
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

export async function fetchSheetResult(matchId: number) {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/sheet-result`, {
    headers: authHeaders(),
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

// ── Retry Unmatched Players ──────────────────────────────────────────────────

export async function retryUnmatchedV2(
  matchId: number,
  nameCorrections: Record<string, string>
): Promise<{ points: any; sheet_result: any; all_matched: boolean }> {
  const res = await fetch(`${BASE}/api/v2/matches/${matchId}/retry-unmatched`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ name_corrections: nameCorrections }),
  });
  return handleResponse(res);
}

// ── Match Discovery (manual only) ───────────────────────────────────────────

export async function triggerDiscovery() {
  const res = await fetch(`${BASE}/api/v2/sync-matches`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse(res);
}
