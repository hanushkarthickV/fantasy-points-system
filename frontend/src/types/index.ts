// ── Scraping / Metadata ────────────────────────────────────────────────────────

export interface BattingEntry {
  name: string;
  dismissal: string;
  runs: number;
  balls: number;
  minutes: number;
  fours: number;
  sixes: number;
  strike_rate: number;
  is_not_out: boolean;
}

export interface BowlingEntry {
  name: string;
  overs: number;
  maidens: number;
  runs_conceded: number;
  wickets: number;
  economy: number;
  dot_balls: number;
  wides: number;
  no_balls: number;
}

export interface FieldingEntry {
  name: string;
  catches: number;
  stumpings: number;
  run_out_direct: number;
  run_out_indirect: number;
}

export interface DismissalDetail {
  batter_name: string;
  dismissal_type: string;
  bowler_name: string | null;
  fielder_name: string | null;
  is_direct_run_out: boolean;
}

export interface InningsData {
  team_name: string;
  batting: BattingEntry[];
  bowling: BowlingEntry[];
  fielding: FieldingEntry[];
  did_not_bat: string[];
  dismissals: DismissalDetail[];
  extras: number;
  total_runs: number;
  total_wickets: number;
  total_overs: number;
}

export interface MatchMetadata {
  match_id: string;
  match_title: string;
  venue: string;
  date: string;
  team1: string;
  team2: string;
  result: string;
  innings: InningsData[];
  url: string;
}

// ── Points ────────────────────────────────────────────────────────────────────

export interface BattingPointsBreakdown {
  run_points: number;
  four_bonus: number;
  six_bonus: number;
  milestone_bonus: number;
  duck_penalty: number;
  strike_rate_bonus: number;
  total: number;
}

export interface BowlingPointsBreakdown {
  wicket_points: number;
  maiden_bonus: number;
  lbw_bowled_bonus: number;
  haul_bonus: number;
  dot_ball_points: number;
  economy_bonus: number;
  total: number;
}

export interface FieldingPointsBreakdown {
  catch_points: number;
  catch_bonus: number;
  stumping_points: number;
  run_out_points: number;
  total: number;
}

export interface PlayerPoints {
  name: string;
  team: string;
  batting: BattingPointsBreakdown | null;
  bowling: BowlingPointsBreakdown | null;
  fielding: FieldingPointsBreakdown | null;
  total_points: number;
}

export interface MatchPoints {
  match_id: string;
  players: PlayerPoints[];
}

// ── Sheet Update ──────────────────────────────────────────────────────────────

export interface PlayerUpdateResult {
  scraped_name: string;
  matched_name: string;
  match_score: number;
  previous_points: number;
  added_points: number;
  new_points: number;
  specialism: string;
}

export interface SheetUpdateResponse {
  match_id: string;
  updated_players: PlayerUpdateResult[];
  unmatched_players: string[];
}
