import axios from "axios";
import type { MatchMetadata, MatchPoints, SheetUpdateResponse } from "../types";

const client = axios.create({ baseURL: "/api" });

export async function scrapeScorecard(url: string): Promise<MatchMetadata> {
  const { data } = await client.post<MatchMetadata>("/scrape", { url });
  return data;
}

/**
 * Scrape with real-time SSE progress.
 * Calls onProgress(step, message) for each backend event.
 * Returns the final MatchMetadata on success.
 */
export async function scrapeWithProgress(
  url: string,
  onProgress: (step: string, message: string) => void,
): Promise<MatchMetadata> {
  const response = await fetch(
    `/api/scrape-stream?url=${encodeURIComponent(url)}`,
  );

  if (!response.ok) {
    // Non-2xx — read error JSON
    const err = await response.json().catch(() => null);
    throw new Error(
      err?.detail || `Scraping failed (HTTP ${response.status})`,
    );
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: MatchMetadata | null = null;
  let errorMsg: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    // SSE blocks are separated by double newline
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim() || block.trim().startsWith(":")) continue; // keepalive

      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;

      const parsed = JSON.parse(data);
      if (event === "progress") {
        onProgress(parsed.step, parsed.message);
      } else if (event === "done") {
        result = parsed as MatchMetadata;
      } else if (event === "error") {
        errorMsg = parsed.message;
      }
    }
  }

  if (errorMsg) throw new Error(errorMsg);
  if (!result) throw new Error("Stream ended without result");
  return result;
}

export async function calculatePoints(matchId: string): Promise<MatchPoints> {
  const { data } = await client.post<MatchPoints>("/calculate-points", {
    match_id: matchId,
  });
  return data;
}

export async function updateSheet(
  matchId: string
): Promise<SheetUpdateResponse> {
  const { data } = await client.post<SheetUpdateResponse>("/update-sheet", {
    match_id: matchId,
  });
  return data;
}

export async function editPlayers(
  matchId: string,
  edits: { original_name: string; new_name?: string; new_total_points?: number }[]
): Promise<MatchPoints> {
  const { data } = await client.patch<MatchPoints>("/edit-players", {
    match_id: matchId,
    edits,
  });
  return data;
}

export async function retryUnmatched(
  matchId: string,
  nameCorrections: Record<string, string>
): Promise<SheetUpdateResponse> {
  const { data } = await client.post<SheetUpdateResponse>("/retry-unmatched", {
    match_id: matchId,
    name_corrections: nameCorrections,
  });
  return data;
}
