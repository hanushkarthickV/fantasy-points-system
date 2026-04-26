import { Upload, ArrowRight, Loader2 } from "lucide-react";
import type { MatchPoints, PlayerPoints } from "../types";

interface Props {
  points: MatchPoints;
  onApprove: () => Promise<void>;
  loading: boolean;
}

export default function PointsReview({ points, onApprove, loading }: Props) {
  const sorted = [...points.players].sort((a, b) => b.total_points - a.total_points);

  return (
    <div className="space-y-6">
      <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-white mb-1">Fantasy Points Calculated</h2>
        <p className="text-gray-400 text-sm">
          Match ID: {points.match_id} &middot; {points.players.length} players scored
        </p>
      </div>

      {/* Points Table */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-xs uppercase border-b border-gray-700">
                <th className="text-left px-4 py-3">#</th>
                <th className="text-left px-4 py-3">Player</th>
                <th className="text-left px-4 py-3">Team</th>
                <th className="text-center px-3 py-3">Bat</th>
                <th className="text-center px-3 py-3">Bowl</th>
                <th className="text-center px-3 py-3">Field</th>
                <th className="text-center px-3 py-3 font-bold">Total</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p, i) => (
                <PlayerRow key={p.name} player={p} rank={i + 1} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Approve Button */}
      <button
        onClick={onApprove}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl 
                   bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed 
                   text-white font-semibold transition"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Updating spreadsheet...
          </>
        ) : (
          <>
            <Upload className="w-5 h-5" />
            Approve &amp; Update Spreadsheet
            <ArrowRight className="w-5 h-5" />
          </>
        )}
      </button>
    </div>
  );
}

function PlayerRow({ player, rank }: { player: PlayerPoints; rank: number }) {
  const batTotal = player.batting?.total ?? 0;
  const bowlTotal = player.bowling?.total ?? 0;
  const fieldTotal = player.fielding?.total ?? 0;

  return (
    <tr className="border-b border-gray-700/30 hover:bg-gray-700/20">
      <td className="px-4 py-2 text-gray-500 font-mono text-xs">{rank}</td>
      <td className="px-4 py-2 font-medium text-white whitespace-nowrap">{player.name}</td>
      <td className="px-4 py-2 text-gray-400 text-xs">{player.team}</td>
      <td className="text-center px-3 py-2">
        <PointsBadge value={batTotal} />
      </td>
      <td className="text-center px-3 py-2">
        <PointsBadge value={bowlTotal} />
      </td>
      <td className="text-center px-3 py-2">
        <PointsBadge value={fieldTotal} />
      </td>
      <td className="text-center px-3 py-2">
        <span
          className={`inline-block px-2 py-0.5 rounded-md font-bold text-sm ${
            player.total_points >= 50
              ? "bg-emerald-500/20 text-emerald-300"
              : player.total_points >= 0
              ? "bg-gray-700 text-white"
              : "bg-red-500/20 text-red-300"
          }`}
        >
          {player.total_points}
        </span>
      </td>
    </tr>
  );
}

function PointsBadge({ value }: { value: number }) {
  if (value === 0) return <span className="text-gray-600">-</span>;
  return (
    <span className={value > 0 ? "text-gray-300" : "text-red-400"}>
      {value > 0 ? `+${value}` : value}
    </span>
  );
}
