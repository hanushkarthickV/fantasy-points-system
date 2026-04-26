import { useState } from "react";
import { CheckCircle2, AlertTriangle, RotateCcw, Loader2, Send } from "lucide-react";
import type { SheetUpdateResponse } from "../types";

interface Props {
  result: SheetUpdateResponse;
  onReset: () => void;
  onRetryUnmatched: (corrections: Record<string, string>) => Promise<void>;
  retryLoading: boolean;
}

export default function UpdateResults({ result, onReset, onRetryUnmatched, retryLoading }: Props) {
  // Name corrections: {display_name_from_unmatched: user_typed_correct_name}
  const [corrections, setCorrections] = useState<Record<string, string>>({});

  const handleCorrectionChange = (unmatchedEntry: string, value: string) => {
    setCorrections((prev) => ({ ...prev, [unmatchedEntry]: value }));
  };

  const handleRetry = () => {
    // Only send non-empty corrections
    const nonEmpty = Object.fromEntries(
      Object.entries(corrections).filter(([, v]) => v.trim())
    );
    if (Object.keys(nonEmpty).length > 0) {
      onRetryUnmatched(nonEmpty);
    }
  };

  const filledCorrections = Object.values(corrections).filter((v) => v.trim()).length;

  return (
    <div className="space-y-6">
      {/* Success Banner */}
      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-6 flex items-start gap-4">
        <CheckCircle2 className="w-7 h-7 text-emerald-400 flex-shrink-0 mt-0.5" />
        <div>
          <h2 className="text-xl font-bold text-emerald-300">Spreadsheet Updated</h2>
          <p className="text-emerald-200/70 text-sm mt-1">
            {result.updated_players.length} player(s) updated for match {result.match_id}
          </p>
        </div>
      </div>

      {/* Updated Players Table */}
      {result.updated_players.length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-700">
            <h3 className="text-lg font-semibold text-white">Updated Players</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-xs uppercase border-b border-gray-700/50">
                  <th className="text-left px-4 py-3">Scraped Name</th>
                  <th className="text-left px-4 py-3">Matched Name</th>
                  <th className="text-center px-3 py-3">Match %</th>
                  <th className="text-center px-3 py-3">Specialism</th>
                  <th className="text-right px-4 py-3">Previous</th>
                  <th className="text-right px-4 py-3">Added</th>
                  <th className="text-right px-4 py-3 font-bold">New Total</th>
                </tr>
              </thead>
              <tbody>
                {result.updated_players.map((p) => (
                  <tr
                    key={p.scraped_name}
                    className="border-b border-gray-700/30 hover:bg-gray-700/20"
                  >
                    <td className="px-4 py-2 text-gray-300">{p.scraped_name}</td>
                    <td className="px-4 py-2 text-white font-medium">{p.matched_name}</td>
                    <td className="text-center px-3 py-2">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                          p.match_score >= 90
                            ? "bg-emerald-500/20 text-emerald-300"
                            : "bg-yellow-500/20 text-yellow-300"
                        }`}
                      >
                        {p.match_score}%
                      </span>
                    </td>
                    <td className="text-center px-3 py-2 text-gray-400 text-xs">
                      {p.specialism || "-"}
                    </td>
                    <td className="text-right px-4 py-2 text-gray-400">{p.previous_points}</td>
                    <td className="text-right px-4 py-2">
                      <span className="text-emerald-400 font-semibold">+{p.added_points}</span>
                    </td>
                    <td className="text-right px-4 py-2 text-white font-bold">{p.new_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Unmatched Players — with correction inputs */}
      {result.unmatched_players.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <h3 className="text-lg font-semibold text-yellow-300">Unmatched Players</h3>
          </div>
          <p className="text-yellow-200/60 text-sm mb-4">
            These players could not be matched in the spreadsheet. Type the correct name from the sheet to update them.
          </p>
          <div className="space-y-3">
            {result.unmatched_players.map((entry) => {
              const scrapedName = entry.split(" (best:")[0].trim();
              return (
                <div key={entry} className="flex items-center gap-3">
                  <span className="text-yellow-200/80 text-sm w-48 shrink-0 truncate" title={entry}>
                    {scrapedName}
                  </span>
                  <span className="text-gray-500 text-sm shrink-0">&rarr;</span>
                  <input
                    type="text"
                    placeholder="Correct name from sheet"
                    value={corrections[entry] || ""}
                    onChange={(e) => handleCorrectionChange(entry, e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-600 text-white text-sm
                               placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-yellow-500"
                  />
                </div>
              );
            })}
          </div>
          {filledCorrections > 0 && (
            <button
              onClick={handleRetry}
              disabled={retryLoading}
              className="mt-4 flex items-center gap-2 px-5 py-2 rounded-lg bg-yellow-600 hover:bg-yellow-500
                         disabled:opacity-50 text-white font-semibold text-sm transition"
            >
              {retryLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Update {filledCorrections} Player(s)
            </button>
          )}
        </div>
      )}

      {/* Reset */}
      <button
        onClick={onReset}
        className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl 
                   bg-gray-700 hover:bg-gray-600 text-white font-semibold transition"
      >
        <RotateCcw className="w-5 h-5" />
        Process Another Match
      </button>
    </div>
  );
}
