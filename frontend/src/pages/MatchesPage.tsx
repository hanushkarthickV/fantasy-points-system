import { useEffect, useState, useCallback, useRef } from "react";
import {
  RefreshCw,
  Play,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Calculator,
  FileSpreadsheet,
  LogOut,
  Loader2,
  Eye,
  ArrowLeft,
  History,
  Info,
  MapPin,
  CalendarDays,
  Send,
} from "lucide-react";
import {
  fetchMatches,
  queueExtraction,
  updateSheetV2,
  triggerDiscovery,
  fetchMatchPoints,
  fetchSheetResult,
  editPlayersV2,
  retryUnmatchedV2,
  type MatchItem,
} from "../services/api_v2";
import PointsReview from "../components/PointsReview";
import type { MatchPoints, SheetUpdateResponse } from "../types";

// ── Status badge config ──────────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  scheduled: { label: "Scheduled", color: "bg-gray-700 text-gray-300", icon: Clock },
  completed: { label: "Completed", color: "bg-blue-500/20 text-blue-300", icon: CheckCircle2 },
  queued: { label: "Queued", color: "bg-yellow-500/20 text-yellow-300", icon: Clock },
  extracting: { label: "Extracting...", color: "bg-yellow-500/20 text-yellow-300", icon: Loader2 },
  points_calculated: { label: "Points Ready", color: "bg-purple-500/20 text-purple-300", icon: Calculator },
  sheet_updated: { label: "Sheet Updated", color: "bg-green-500/20 text-green-300", icon: FileSpreadsheet },
  extraction_failed: { label: "Failed", color: "bg-red-500/20 text-red-300", icon: AlertTriangle },
  manually_extracted: { label: "Manual", color: "bg-gray-600/30 text-gray-400", icon: CheckCircle2 },
};

interface MatchesPageProps {
  email: string;
  onLogout: () => void;
}

export default function MatchesPage({ email, onLogout }: MatchesPageProps) {
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Review modal state
  const [reviewMatchId, setReviewMatchId] = useState<number | null>(null);
  const [reviewPoints, setReviewPoints] = useState<MatchPoints | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewMatch, setReviewMatch] = useState<MatchItem | null>(null);
  const [reviewSheetResult, setReviewSheetResult] = useState<SheetUpdateResponse | null>(null);
  const [sheetUpdateLoading, setSheetUpdateLoading] = useState(false);
  const [reviewMode, setReviewMode] = useState<"review" | "history">("review");
  const [retryLoading, setRetryLoading] = useState(false);

  // Last sync time (from DB via API, shared across all users/sessions)
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);

  // Auto-poll ref
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadMatches = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchMatches();
      setMatches(res.matches);
      if (res.last_sync_time) setLastSyncTime(res.last_sync_time);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  // Auto-poll: if any match is queued or extracting, refresh every 5s
  useEffect(() => {
    const hasActive = matches.some((m) => m.status === "queued" || m.status === "extracting");
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetchMatches();
          setMatches(res.matches);
          if (res.last_sync_time) setLastSyncTime(res.last_sync_time);
        } catch { /* ignore */ }
      }, 5000);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [matches]);

  // ── Discovery ──────────────────────────────────────────────────────────────

  const handleDiscovery = async () => {
    setDiscoveryLoading(true);
    setError(null);
    try {
      await triggerDiscovery();
      await loadMatches(); // loadMatches picks up last_sync_time from API
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDiscoveryLoading(false);
    }
  };

  // ── Queue Extraction ───────────────────────────────────────────────────────

  const handleQueueExtract = async (matchId: number) => {
    setError(null);
    try {
      await queueExtraction(matchId);
      // Optimistically update
      setMatches((prev) =>
        prev.map((m) => (m.id === matchId ? { ...m, status: "queued" } : m))
      );
    } catch (err: any) {
      setError(err.message);
    }
  };

  // ── Review Points (open) ───────────────────────────────────────────────────

  const handleOpenReview = async (matchId: number, mode: "review" | "history" = "review") => {
    setReviewLoading(true);
    setError(null);
    setReviewSheetResult(null);
    setReviewMode(mode);
    const match = matches.find((m) => m.id === matchId) || null;
    setReviewMatch(match);
    try {
      const pts = await fetchMatchPoints(matchId);
      setReviewPoints(pts as MatchPoints);
      setReviewMatchId(matchId);

      // Load existing sheet result (for both review and history, to restore state)
      try {
        const sr = await fetchSheetResult(matchId);
        setReviewSheetResult(sr as SheetUpdateResponse);
      } catch { /* no sheet result yet — that's fine */ }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setReviewLoading(false);
    }
  };

  const handleCloseReview = () => {
    setReviewMatchId(null);
    setReviewPoints(null);
    setReviewMatch(null);
    setReviewSheetResult(null);
    loadMatches(); // Refresh list on close
  };

  // ── Edit Players ───────────────────────────────────────────────────────────

  const handleReviewEditPlayers = async (
    edits: { original_name: string; new_name?: string; new_total_points?: number }[]
  ) => {
    if (!reviewMatchId) return;
    try {
      const updated = await editPlayersV2(reviewMatchId, edits);
      setReviewPoints(updated as MatchPoints);
      // Clear previous sheet results since data changed
      setReviewSheetResult(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  // ── Update Sheet (stays on review screen!) ─────────────────────────────────

  const handleReviewApprove = async () => {
    if (!reviewMatchId) return;
    setSheetUpdateLoading(true);
    setError(null);
    try {
      const result = await updateSheetV2(reviewMatchId);
      setReviewSheetResult(result as SheetUpdateResponse);
      // Update match status in local list
      setMatches((prev) =>
        prev.map((m) => (m.id === reviewMatchId ? { ...m, status: "sheet_updated" } : m))
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSheetUpdateLoading(false);
    }
  };

  // ── Retry Unmatched Players ────────────────────────────────────────────────

  const handleRetryUnmatched = async (nameCorrections: Record<string, string>) => {
    if (!reviewMatchId) return;
    setRetryLoading(true);
    setError(null);
    try {
      const { points, sheet_result, all_matched } = await retryUnmatchedV2(reviewMatchId, nameCorrections);
      // Update the player list with corrected/renamed names
      setReviewPoints(points as MatchPoints);
      // Merge newly matched into existing sheet result
      setReviewSheetResult((prev) => {
        if (!prev) return sheet_result as SheetUpdateResponse;
        return {
          ...prev,
          updated_players: [...prev.updated_players, ...sheet_result.updated_players],
          unmatched_players: sheet_result.unmatched_players,
        };
      });
      // If all matched, update status in local list → enables History button
      if (all_matched) {
        setMatches((prev) =>
          prev.map((m) => (m.id === reviewMatchId ? { ...m, status: "sheet_updated" } : m))
        );
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRetryLoading(false);
    }
  };

  // ── Row Actions ────────────────────────────────────────────────────────────

  const getActions = (match: MatchItem) => {
    const actions: JSX.Element[] = [];

    // Scheduled matches — disabled with tooltip
    if (match.status === "scheduled") {
      actions.push(
        <span
          key="disabled"
          className="px-3 py-1.5 bg-gray-700/50 text-gray-500 text-xs font-medium rounded-lg flex items-center gap-1.5 cursor-not-allowed"
          title="Extraction possible only after the completion of the match"
        >
          <Info className="w-3 h-3" /> Awaiting result
        </span>
      );
      return actions;
    }

    // Extract button for completed / failed
    if (match.status === "completed" || match.status === "extraction_failed") {
      actions.push(
        <button
          key="extract"
          onClick={() => handleQueueExtract(match.id)}
          className="px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
        >
          <Play className="w-3 h-3" /> Extract
        </button>
      );
    }

    // Queued — show waiting state
    if (match.status === "queued") {
      actions.push(
        <span
          key="queued"
          className="px-3 py-1.5 bg-yellow-500/10 text-yellow-300 text-xs font-medium rounded-lg flex items-center gap-1.5"
        >
          <Clock className="w-3 h-3" /> In Queue
        </span>
      );
    }

    // Extracting — show spinner
    if (match.status === "extracting") {
      actions.push(
        <span
          key="extracting"
          className="px-3 py-1.5 bg-yellow-500/10 text-yellow-300 text-xs font-medium rounded-lg flex items-center gap-1.5"
        >
          <Loader2 className="w-3 h-3 animate-spin" /> Extracting...
        </span>
      );
    }

    // Points Ready — Review button
    if (match.status === "points_calculated") {
      actions.push(
        <button
          key="review"
          onClick={() => handleOpenReview(match.id, "review")}
          disabled={reviewLoading}
          className="px-3 py-1.5 bg-purple-500 hover:bg-purple-600 disabled:bg-purple-500/50 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
        >
          {reviewLoading && reviewMatch?.id === match.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
          Review Points
        </button>
      );
    }

    // Sheet Updated — History button (only after sheet is updated, not alongside Review)
    if (match.status === "sheet_updated") {
      actions.push(
        <button
          key="history"
          onClick={() => handleOpenReview(match.id, "history")}
          disabled={reviewLoading}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700/50 text-gray-300 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
        >
          <History className="w-3 h-3" /> History
        </button>
      );
    }

    // Manually extracted — re-extract
    if (match.status === "manually_extracted") {
      actions.push(
        <button
          key="reextract"
          onClick={() => handleQueueExtract(match.id)}
          className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
        >
          <Play className="w-3 h-3" /> Re-extract
        </button>
      );
    }

    return actions;
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
              <FileSpreadsheet className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">
                Fantasy Points System
                <span className="ml-2 text-xs font-normal text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">v2.0</span>
              </h1>
              <p className="text-xs text-gray-500">IPL 2026 • Automated Match Extraction &amp; Points Calculation</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">{email}</span>
            <button
              onClick={onLogout}
              className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={loadMatches}
              disabled={loading}
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg flex items-center gap-2 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
            <button
              onClick={handleDiscovery}
              disabled={discoveryLoading}
              className="px-3 py-2 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-sm rounded-lg flex items-center gap-2 transition-colors"
            >
              {discoveryLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Sync Matches
            </button>
          </div>
          <div className="flex items-center gap-3">
            {lastSyncTime && (
              <span className="text-xs text-gray-500">
                Last synced: {new Date(lastSyncTime).toLocaleString("en-IN", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
                })}
              </span>
            )}
            <span className="text-sm text-gray-500">{matches.length} matches</span>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex items-center justify-between">
            <span className="text-sm text-red-300">{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 text-xs hover:text-red-300">
              Dismiss
            </button>
          </div>
        )}

        {/* Match list */}
        {loading && matches.length === 0 ? (
          <div className="text-center py-20">
            <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto mb-3" />
            <p className="text-gray-400">Loading matches...</p>
          </div>
        ) : matches.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400">No matches found. Click "Sync Matches" to discover them.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {matches.map((match) => {
              const cfg = STATUS_CONFIG[match.status] || STATUS_CONFIG.scheduled;
              const Icon = cfg.icon;
              const isScheduled = match.status === "scheduled";
              return (
                <div
                  key={match.id}
                  className={`bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between gap-4 transition-colors ${
                    isScheduled ? "opacity-60" : "hover:border-gray-700"
                  }`}
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    {/* Match number */}
                    <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
                      <span className="text-sm font-bold text-gray-300">
                        {match.match_number || "?"}
                      </span>
                    </div>

                    {/* Match info */}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-white truncate">
                        {match.team1 && match.team2
                          ? `${match.team1} vs ${match.team2}`
                          : match.title || `Match ${match.espn_match_id}`}
                      </p>
                      <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                        {match.result_text && (
                          <span className="text-xs text-gray-400 truncate">{match.result_text}</span>
                        )}
                        {match.venue && (
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <MapPin className="w-3 h-3" />{match.venue}
                          </span>
                        )}
                        {match.match_date && (
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <CalendarDays className="w-3 h-3" />
                            {new Date(match.match_date).toLocaleDateString("en-IN", {
                              day: "numeric", month: "short", year: "numeric"
                            })}
                            {" "}
                            {new Date(match.match_date).toLocaleTimeString("en-IN", {
                              hour: "2-digit", minute: "2-digit"
                            })}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Status badge */}
                  <div className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 flex-shrink-0 ${cfg.color}`}>
                    <Icon className={`w-3 h-3 ${match.status === "extracting" ? "animate-spin" : ""}`} />
                    {cfg.label}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {getActions(match)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* ── Review Points Full-screen Overlay ────────────────────────────── */}
      {reviewMatchId && reviewPoints && (
        <div className="fixed inset-0 z-[100] bg-gray-950 overflow-y-auto">
          {/* Modal header */}
          <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
            <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
              <button
                onClick={handleCloseReview}
                className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
                title="Back to matches"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex-1 min-w-0">
                <h1 className="text-lg font-bold text-white truncate">
                  {reviewMode === "history" ? "Match History" : "Review Points"} — {reviewMatch?.team1 && reviewMatch?.team2
                    ? `${reviewMatch.team1} vs ${reviewMatch.team2}`
                    : `Match #${reviewMatch?.match_number || reviewMatchId}`}
                </h1>
                <p className="text-xs text-gray-500">
                  {reviewMode === "history"
                    ? "View calculated points and sheet update results"
                    : "Edit player names or points, then approve to update the spreadsheet"}
                </p>
              </div>
            </div>
          </header>

          <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
            {/* REVIEW MODE: full PointsReview with edit + approve */}
            {reviewMode === "review" && (
              <>
                <PointsReview
                  points={reviewPoints}
                  onApprove={handleReviewApprove}
                  onEditPlayers={handleReviewEditPlayers}
                  loading={sheetUpdateLoading}
                  hideApprove={!!reviewSheetResult}
                />

                {/* Sheet Update Results (shown INLINE after update, stays on screen) */}
                {reviewSheetResult && (
                  <SheetResultsPanel
                    result={reviewSheetResult}
                    onRetry={handleRetryUnmatched}
                    retryLoading={retryLoading}
                  />
                )}
              </>
            )}

            {/* HISTORY MODE: read-only — only sheet update results, no edit/approve */}
            {reviewMode === "history" && (
              <>
                {/* Read-only points summary */}
                <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
                  <h2 className="text-xl font-bold text-white mb-1">Fantasy Points Summary</h2>
                  <p className="text-gray-400 text-sm">
                    {reviewPoints.players.length} players scored
                  </p>
                </div>
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-gray-400 text-xs uppercase border-b border-gray-700/50">
                          <th className="text-left px-4 py-2">#</th>
                          <th className="text-left px-4 py-2">Player</th>
                          <th className="text-left px-4 py-2">Team</th>
                          <th className="text-center px-3 py-2">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...reviewPoints.players]
                          .sort((a, b) => b.total_points - a.total_points)
                          .map((p, i) => (
                          <tr key={p.name} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                            <td className="px-4 py-2 text-gray-500 font-mono text-xs">{i + 1}</td>
                            <td className="px-4 py-2 font-medium text-white">{p.name}</td>
                            <td className="px-4 py-2 text-gray-400 text-xs">{p.team}</td>
                            <td className="text-center px-3 py-2 font-bold text-white">{p.total_points}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* No sheet results table in history mode — only shown in review mode */}
              </>
            )}
          </main>
        </div>
      )}
    </div>
  );
}

// ── Sheet Results Panel (reused in both review and history) ─────────────────

function SheetResultsPanel({
  result,
  onRetry,
  retryLoading,
  readOnly,
}: {
  result: SheetUpdateResponse;
  onRetry?: (corrections: Record<string, string>) => Promise<void>;
  retryLoading?: boolean;
  readOnly?: boolean;
}) {
  const [corrections, setCorrections] = useState<Record<string, string>>({});

  const handleRetryClick = () => {
    if (!onRetry) return;
    // Only send corrections where user actually typed something
    const filled: Record<string, string> = {};
    for (const [key, val] of Object.entries(corrections)) {
      if (val.trim()) filled[key] = val.trim();
    }
    if (Object.keys(filled).length === 0) return;
    onRetry(filled);
    setCorrections({});
  };

  // Parse "PlayerName (best: SomeName, score: 71)" into parts
  const parseUnmatched = (raw: string) => {
    const match = raw.match(/^(.+?)\s*\(best:\s*(.+?),\s*score:\s*(\d+)\)$/);
    if (match) return { displayKey: raw, scrapedName: match[1].trim(), bestMatch: match[2].trim(), score: parseInt(match[3]) };
    return { displayKey: raw, scrapedName: raw, bestMatch: null, score: null };
  };

  return (
    <div className="space-y-4">
      <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-green-300 mb-2 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Sheet Updated Successfully
        </h3>
        <p className="text-xs text-green-200/70">
          {result.updated_players.length} player(s) matched &middot;{" "}
          {result.unmatched_players.length} unmatched
        </p>
      </div>

      {/* Matched Players Table */}
      {result.updated_players.length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700">
            <h4 className="text-sm font-semibold text-white">
              Matched Players ({result.updated_players.length})
            </h4>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-xs uppercase border-b border-gray-700/50">
                  <th className="text-left px-4 py-2">Scraped Name</th>
                  <th className="text-left px-4 py-2">Sheet Name</th>
                  <th className="text-center px-3 py-2">Match %</th>
                  <th className="text-center px-3 py-2">Prev</th>
                  <th className="text-center px-3 py-2">Added</th>
                  <th className="text-center px-3 py-2">New</th>
                </tr>
              </thead>
              <tbody>
                {result.updated_players.map((p, i) => (
                  <tr key={i} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                    <td className="px-4 py-2 text-gray-300">{p.scraped_name}</td>
                    <td className="px-4 py-2 font-medium text-white">{p.matched_name}</td>
                    <td className="text-center px-3 py-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                        p.match_score >= 90
                          ? "bg-emerald-500/20 text-emerald-300"
                          : p.match_score >= 70
                          ? "bg-yellow-500/20 text-yellow-300"
                          : "bg-red-500/20 text-red-300"
                      }`}>
                        {p.match_score}%
                      </span>
                    </td>
                    <td className="text-center px-3 py-2 text-gray-400">{p.previous_points}</td>
                    <td className="text-center px-3 py-2 text-emerald-400">+{p.added_points}</td>
                    <td className="text-center px-3 py-2 font-semibold text-white">{p.new_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Unmatched Players — interactive correction form (review mode) or read-only (history) */}
      {result.unmatched_players.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-red-300 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Unmatched Players ({result.unmatched_players.length})
          </h4>

          {!readOnly && onRetry ? (
            <>
              <p className="text-xs text-red-200/70 mb-4">
                Type the correct name (as it appears in the Google Sheet) for each player, then click "Retry Update".
              </p>
              <div className="space-y-3">
                {result.unmatched_players.map((raw) => {
                  const { displayKey, scrapedName, bestMatch, score } = parseUnmatched(raw);
                  return (
                    <div key={displayKey} className="flex items-center gap-3 flex-wrap">
                      <div className="min-w-[180px]">
                        <span className="text-sm font-medium text-red-200">{scrapedName}</span>
                        {bestMatch && (
                          <span className="ml-2 text-xs text-gray-500">
                            closest: {bestMatch} ({score}%)
                          </span>
                        )}
                      </div>
                      <input
                        type="text"
                        placeholder={bestMatch || "Correct sheet name"}
                        value={corrections[displayKey] || ""}
                        onChange={(e) =>
                          setCorrections((prev) => ({ ...prev, [displayKey]: e.target.value }))
                        }
                        className="flex-1 min-w-[200px] bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  );
                })}
              </div>
              <button
                onClick={handleRetryClick}
                disabled={retryLoading || Object.values(corrections).every((v) => !v.trim())}
                className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg flex items-center gap-2 transition-colors"
              >
                {retryLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Retry Update
              </button>
            </>
          ) : (
            <div className="flex flex-wrap gap-2 mt-2">
              {result.unmatched_players.map((raw, i) => {
                const { scrapedName } = parseUnmatched(raw);
                return (
                  <span
                    key={i}
                    className="px-3 py-1 rounded-lg bg-red-500/20 text-red-300 text-xs font-medium"
                  >
                    {scrapedName}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
