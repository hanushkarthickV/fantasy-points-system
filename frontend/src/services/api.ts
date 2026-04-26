import axios from "axios";
import type { MatchMetadata, MatchPoints, SheetUpdateResponse } from "../types";

const client = axios.create({ baseURL: "/api" });

export async function scrapeScorecard(url: string): Promise<MatchMetadata> {
  const { data } = await client.post<MatchMetadata>("/scrape", { url });
  return data;
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
