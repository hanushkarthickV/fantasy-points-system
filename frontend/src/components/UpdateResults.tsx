import { CheckCircle2, AlertTriangle, RotateCcw } from "lucide-react";
import type { SheetUpdateResponse } from "../types";

interface Props {
  result: SheetUpdateResponse;
  onReset: () => void;
}

export default function UpdateResults({ result, onReset }: Props) {
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

      {/* Unmatched Players */}
      {result.unmatched_players.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <h3 className="text-lg font-semibold text-yellow-300">Unmatched Players</h3>
          </div>
          <ul className="space-y-1">
            {result.unmatched_players.map((name) => (
              <li key={name} className="text-yellow-200/70 text-sm">
                {name}
              </li>
            ))}
          </ul>
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
