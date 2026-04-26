import { CheckCircle, ArrowRight, Loader2 } from "lucide-react";
import type { MatchMetadata, InningsData } from "../types";

interface Props {
  metadata: MatchMetadata;
  onApprove: () => Promise<void>;
  loading: boolean;
}

export default function ScorecardReview({ metadata, onApprove, loading }: Props) {
  return (
    <div className="space-y-6">
      {/* Match Header */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-white mb-1">{metadata.match_title}</h2>
        <p className="text-gray-400 text-sm">{metadata.result}</p>
        <div className="flex gap-4 mt-3 text-sm text-gray-500">
          <span>{metadata.venue}</span>
          <span>{metadata.date}</span>
        </div>
      </div>

      {/* Innings */}
      {metadata.innings.map((inn, idx) => (
        <InningsCard key={idx} innings={inn} />
      ))}

      {/* Approve Button */}
      <button
        onClick={onApprove}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl 
                   bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed 
                   text-white font-semibold transition"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Calculating points...
          </>
        ) : (
          <>
            <CheckCircle className="w-5 h-5" />
            Approve &amp; Calculate Points
            <ArrowRight className="w-5 h-5" />
          </>
        )}
      </button>
    </div>
  );
}

function InningsCard({ innings }: { innings: InningsData }) {
  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
      <div className="px-6 py-4 bg-gray-800 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-white">
          {innings.team_name}
          <span className="text-gray-400 text-sm font-normal ml-3">
            {innings.total_runs}/{innings.total_wickets} ({innings.total_overs} ov)
          </span>
        </h3>
      </div>

      {/* Batting */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-xs uppercase border-b border-gray-700/50">
              <th className="text-left px-4 py-2">Batter</th>
              <th className="text-left px-4 py-2">Dismissal</th>
              <th className="text-center px-3 py-2">R</th>
              <th className="text-center px-3 py-2">B</th>
              <th className="text-center px-3 py-2">4s</th>
              <th className="text-center px-3 py-2">6s</th>
              <th className="text-center px-3 py-2">SR</th>
            </tr>
          </thead>
          <tbody>
            {innings.batting.map((b, i) => (
              <tr key={i} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                <td className="px-4 py-2 font-medium text-white whitespace-nowrap">
                  {b.name}
                  {b.is_not_out && <span className="text-emerald-400 ml-1">*</span>}
                </td>
                <td className="px-4 py-2 text-gray-400 max-w-[200px] truncate">{b.dismissal}</td>
                <td className="text-center px-3 py-2 font-semibold text-white">{b.runs}</td>
                <td className="text-center px-3 py-2 text-gray-400">{b.balls}</td>
                <td className="text-center px-3 py-2 text-gray-400">{b.fours}</td>
                <td className="text-center px-3 py-2 text-gray-400">{b.sixes}</td>
                <td className="text-center px-3 py-2 text-gray-400">{b.strike_rate.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bowling */}
      <div className="border-t border-gray-700">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-xs uppercase border-b border-gray-700/50">
                <th className="text-left px-4 py-2">Bowler</th>
                <th className="text-center px-3 py-2">O</th>
                <th className="text-center px-3 py-2">M</th>
                <th className="text-center px-3 py-2">R</th>
                <th className="text-center px-3 py-2">W</th>
                <th className="text-center px-3 py-2">Econ</th>
                <th className="text-center px-3 py-2">Dots</th>
              </tr>
            </thead>
            <tbody>
              {innings.bowling.map((bw, i) => (
                <tr key={i} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                  <td className="px-4 py-2 font-medium text-white whitespace-nowrap">{bw.name}</td>
                  <td className="text-center px-3 py-2 text-gray-400">{bw.overs}</td>
                  <td className="text-center px-3 py-2 text-gray-400">{bw.maidens}</td>
                  <td className="text-center px-3 py-2 text-gray-400">{bw.runs_conceded}</td>
                  <td className="text-center px-3 py-2 font-semibold text-white">{bw.wickets}</td>
                  <td className="text-center px-3 py-2 text-gray-400">{bw.economy.toFixed(2)}</td>
                  <td className="text-center px-3 py-2 text-gray-400">{bw.dot_balls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Fielding */}
      {innings.fielding.length > 0 && (
        <div className="border-t border-gray-700 px-6 py-3">
          <p className="text-xs uppercase text-gray-400 mb-2 font-semibold">Fielding</p>
          <div className="flex flex-wrap gap-2">
            {innings.fielding.map((f, i) => (
              <span
                key={i}
                className="px-3 py-1 rounded-lg bg-gray-700/50 text-gray-300 text-xs"
              >
                {f.name}
                {f.catches > 0 && ` — ${f.catches} ct`}
                {f.stumpings > 0 && ` — ${f.stumpings} st`}
                {f.run_out_direct > 0 && ` — ${f.run_out_direct} ro(d)`}
                {f.run_out_indirect > 0 && ` — ${f.run_out_indirect} ro`}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
