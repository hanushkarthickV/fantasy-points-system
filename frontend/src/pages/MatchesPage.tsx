import { useEffect, useState } from "react";
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
} from "lucide-react";
import {
  fetchMatches,
  extractMatchStream,
  calculatePointsV2,
  updateSheetV2,
  triggerDiscovery,
  type MatchItem,
} from "../services/api_v2";

// ── Status badge config ──────────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  scheduled: { label: "Scheduled", color: "bg-gray-700 text-gray-300", icon: Clock },
  completed: { label: "Completed", color: "bg-blue-500/20 text-blue-300", icon: CheckCircle2 },
  extracting: { label: "Extracting...", color: "bg-yellow-500/20 text-yellow-300", icon: Loader2 },
  extracted: { label: "Extracted", color: "bg-emerald-500/20 text-emerald-300", icon: CheckCircle2 },
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
  const [extractingId, setExtractingId] = useState<number | null>(null);
  const [progressMsg, setProgressMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const loadMatches = async () => {
    setLoading(true);
    try {
      const res = await fetchMatches();
      setMatches(res.matches);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatches();
  }, []);

  const handleDiscovery = async () => {
    setDiscoveryLoading(true);
    setError(null);
    try {
      const res = await triggerDiscovery();
      await loadMatches();
      if (res.new_matches > 0) {
        setError(null);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDiscoveryLoading(false);
    }
  };

  const handleExtract = (matchId: number) => {
    setExtractingId(matchId);
    setProgressMsg("Starting extraction...");
    setError(null);

    // Optimistically update status
    setMatches((prev) =>
      prev.map((m) => (m.id === matchId ? { ...m, status: "extracting" } : m))
    );

    extractMatchStream(
      matchId,
      (_step, message) => setProgressMsg(message),
      (_data) => {
        setExtractingId(null);
        setProgressMsg("");
        setMatches((prev) =>
          prev.map((m) => (m.id === matchId ? { ...m, status: "extracted" } : m))
        );
      },
      (message) => {
        setExtractingId(null);
        setProgressMsg("");
        setError(message);
        setMatches((prev) =>
          prev.map((m) => (m.id === matchId ? { ...m, status: "extraction_failed" } : m))
        );
      }
    );
  };

  const handleCalculate = async (matchId: number) => {
    setActionLoading(matchId);
    setError(null);
    try {
      await calculatePointsV2(matchId);
      setMatches((prev) =>
        prev.map((m) => (m.id === matchId ? { ...m, status: "points_calculated" } : m))
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateSheet = async (matchId: number) => {
    setActionLoading(matchId);
    setError(null);
    try {
      await updateSheetV2(matchId);
      setMatches((prev) =>
        prev.map((m) => (m.id === matchId ? { ...m, status: "sheet_updated" } : m))
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const getActions = (match: MatchItem) => {
    const actions: JSX.Element[] = [];
    const isThisLoading = actionLoading === match.id;

    switch (match.status) {
      case "completed":
      case "extraction_failed":
        actions.push(
          <button
            key="extract"
            onClick={() => handleExtract(match.id)}
            disabled={extractingId !== null}
            className="px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-500/50 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <Play className="w-3 h-3" /> Extract
          </button>
        );
        break;
      case "extracted":
        actions.push(
          <button
            key="calculate"
            onClick={() => handleCalculate(match.id)}
            disabled={isThisLoading}
            className="px-3 py-1.5 bg-purple-500 hover:bg-purple-600 disabled:bg-purple-500/50 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
          >
            {isThisLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Calculator className="w-3 h-3" />}
            Calculate
          </button>
        );
        break;
      case "points_calculated":
        actions.push(
          <button
            key="sheet"
            onClick={() => handleUpdateSheet(match.id)}
            disabled={isThisLoading}
            className="px-3 py-1.5 bg-green-500 hover:bg-green-600 disabled:bg-green-500/50 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
          >
            {isThisLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileSpreadsheet className="w-3 h-3" />}
            Update Sheet
          </button>
        );
        break;
      case "manually_extracted":
        actions.push(
          <button
            key="modal-extract"
            onClick={() => handleExtract(match.id)}
            disabled={extractingId !== null}
            className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 disabled:bg-gray-600/50 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <Play className="w-3 h-3" /> Re-extract
          </button>
        );
        break;
    }
    return actions;
  };

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
              <h1 className="text-lg font-bold text-white">Match Listing</h1>
              <p className="text-xs text-gray-500">IPL 2026 Fantasy Points</p>
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
          <span className="text-sm text-gray-500">{matches.length} matches</span>
        </div>

        {/* Extraction progress banner */}
        {extractingId && progressMsg && (
          <div className="mb-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-3 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
            <span className="text-sm text-yellow-200">{progressMsg}</span>
          </div>
        )}

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
              return (
                <div
                  key={match.id}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between gap-4 hover:border-gray-700 transition-colors"
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
                      {match.result_text && (
                        <p className="text-xs text-gray-400 truncate mt-0.5">{match.result_text}</p>
                      )}
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
    </div>
  );
}
