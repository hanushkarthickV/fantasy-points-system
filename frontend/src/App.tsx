import { useState } from "react";
import { Trophy, AlertCircle } from "lucide-react";
import UrlInput from "./components/UrlInput";
import ScorecardReview from "./components/ScorecardReview";
import PointsReview from "./components/PointsReview";
import UpdateResults from "./components/UpdateResults";
import {
  scrapeScorecard,
  calculatePoints,
  updateSheet,
  editPlayers,
  retryUnmatched,
} from "./services/api";
import type { MatchMetadata, MatchPoints, SheetUpdateResponse } from "./types";

type Step = "input" | "review_scorecard" | "review_points" | "done";

const STEP_LABELS: Record<Step, string> = {
  input: "Enter URL",
  review_scorecard: "Review Scorecard",
  review_points: "Review Points",
  done: "Complete",
};

const STEP_ORDER: Step[] = ["input", "review_scorecard", "review_points", "done"];

export default function App() {
  const [step, setStep] = useState<Step>("input");
  const [loading, setLoading] = useState(false);
  const [retryLoading, setRetryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [metadata, setMetadata] = useState<MatchMetadata | null>(null);
  const [points, setPoints] = useState<MatchPoints | null>(null);
  const [updateResult, setUpdateResult] = useState<SheetUpdateResponse | null>(null);

  const handleScrape = async (url: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await scrapeScorecard(url);
      setMetadata(data);
      setStep("review_scorecard");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg || d).join("; "));
      } else {
        setError(err.message || "Scraping failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCalculatePoints = async () => {
    if (!metadata) return;
    setLoading(true);
    setError(null);
    try {
      const data = await calculatePoints(metadata.match_id);
      setPoints(data);
      setStep("review_points");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Points calculation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateSheet = async () => {
    if (!points) return;
    setLoading(true);
    setError(null);
    try {
      const data = await updateSheet(points.match_id);
      setUpdateResult(data);
      setStep("done");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Sheet update failed");
    } finally {
      setLoading(false);
    }
  };

  const handleEditPlayers = async (
    edits: { original_name: string; new_name?: string; new_total_points?: number }[]
  ) => {
    if (!points) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await editPlayers(points.match_id, edits);
      setPoints(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Edit failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRetryUnmatched = async (corrections: Record<string, string>) => {
    if (!updateResult) return;
    setRetryLoading(true);
    setError(null);
    try {
      const retryResult = await retryUnmatched(updateResult.match_id, corrections);
      // Merge results: add newly updated players, remove them from unmatched
      const correctedKeys = new Set(Object.keys(corrections));
      const remainingUnmatched = updateResult.unmatched_players.filter(
        (u) => !correctedKeys.has(u)
      );
      setUpdateResult({
        ...updateResult,
        updated_players: [
          ...updateResult.updated_players,
          ...retryResult.updated_players,
        ],
        unmatched_players: [
          ...remainingUnmatched,
          ...retryResult.unmatched_players,
        ],
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Retry failed");
    } finally {
      setRetryLoading(false);
    }
  };

  const handleReset = () => {
    setStep("input");
    setMetadata(null);
    setPoints(null);
    setUpdateResult(null);
    setError(null);
  };

  const currentIdx = STEP_ORDER.indexOf(step);

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
            <Trophy className="w-5 h-5 text-indigo-400" />
          </div>
          <h1 className="text-lg font-bold text-white">Fantasy Points System</h1>
          <span className="text-xs text-gray-500 ml-2">IPL 2026</span>
        </div>
      </header>

      {/* Step Indicator */}
      <div className="max-w-5xl mx-auto px-6 pt-6 pb-2">
        <div className="flex items-center gap-1">
          {STEP_ORDER.map((s, i) => (
            <div key={s} className="flex items-center gap-1 flex-1">
              <div
                className={`flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold transition-colors ${
                  i < currentIdx
                    ? "bg-emerald-500 text-white"
                    : i === currentIdx
                    ? "bg-indigo-500 text-white"
                    : "bg-gray-800 text-gray-500"
                }`}
              >
                {i < currentIdx ? "\u2713" : i + 1}
              </div>
              <span
                className={`text-xs hidden sm:inline ${
                  i <= currentIdx ? "text-gray-300" : "text-gray-600"
                }`}
              >
                {STEP_LABELS[s]}
              </span>
              {i < STEP_ORDER.length - 1 && (
                <div
                  className={`flex-1 h-px mx-2 ${
                    i < currentIdx ? "bg-emerald-500/50" : "bg-gray-800"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="max-w-5xl mx-auto px-6 pt-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-300 font-medium text-sm">Error</p>
              <p className="text-red-200/70 text-sm mt-1">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-400 hover:text-red-300 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 py-8">
        {step === "input" && (
          <UrlInput onScrape={handleScrape} loading={loading} />
        )}
        {step === "review_scorecard" && metadata && (
          <ScorecardReview
            metadata={metadata}
            onApprove={handleCalculatePoints}
            loading={loading}
          />
        )}
        {step === "review_points" && points && (
          <PointsReview
            points={points}
            onApprove={handleUpdateSheet}
            onEditPlayers={handleEditPlayers}
            loading={loading}
          />
        )}
        {step === "done" && updateResult && (
          <UpdateResults
            result={updateResult}
            onReset={handleReset}
            onRetryUnmatched={handleRetryUnmatched}
            retryLoading={retryLoading}
          />
        )}
      </main>
    </div>
  );
}
