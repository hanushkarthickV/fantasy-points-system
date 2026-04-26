import { useState } from "react";
import { Upload, ArrowRight, Loader2, ChevronDown, Swords, Target, Shield } from "lucide-react";
import type {
  MatchPoints,
  PlayerPoints,
  BattingPointsBreakdown,
  BowlingPointsBreakdown,
  FieldingPointsBreakdown,
} from "../types";

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
          &middot; Click a row to see breakdown
        </p>
      </div>

      {/* Players Accordion */}
      <div className="space-y-2">
        {sorted.map((p, i) => (
          <PlayerAccordion key={p.name} player={p} rank={i + 1} />
        ))}
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

/* ── Accordion per player ──────────────────────────────────────────────────── */

function PlayerAccordion({ player, rank }: { player: PlayerPoints; rank: number }) {
  const [open, setOpen] = useState(false);

  const batTotal = player.batting?.total ?? 0;
  const bowlTotal = player.bowling?.total ?? 0;
  const fieldTotal = player.fielding?.total ?? 0;

  const totalColor =
    player.total_points >= 50
      ? "bg-emerald-500/20 text-emerald-300"
      : player.total_points >= 0
      ? "bg-gray-700 text-white"
      : "bg-red-500/20 text-red-300";

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden transition-all">
      {/* Header Row — always visible */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-700/30 transition"
      >
        <span className="text-gray-500 font-mono text-xs w-6 text-right shrink-0">
          {rank}
        </span>
        <span className="font-medium text-white truncate flex-1">{player.name}</span>
        <span className="text-gray-500 text-xs hidden sm:inline">{player.team}</span>

        <div className="flex items-center gap-3 ml-auto shrink-0">
          <CategoryPill label="BAT" value={batTotal} />
          <CategoryPill label="BOWL" value={bowlTotal} />
          <CategoryPill label="FLD" value={fieldTotal} />
          <span className={`inline-block px-2.5 py-0.5 rounded-md font-bold text-sm ${totalColor}`}>
            {player.total_points}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {/* Expanded Breakdown */}
      {open && (
        <div className="border-t border-gray-700 px-4 py-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {player.batting && <BattingBreakdown b={player.batting} />}
          {player.bowling && <BowlingBreakdown b={player.bowling} />}
          {player.fielding && <FieldingBreakdown b={player.fielding} />}
          {!player.batting && !player.bowling && !player.fielding && (
            <p className="text-gray-500 text-sm col-span-3">No points breakdown available.</p>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Category Pill (compact header badges) ─────────────────────────────────── */

function CategoryPill({ label, value }: { label: string; value: number }) {
  if (value === 0) return null;
  return (
    <span
      className={`hidden sm:inline text-xs px-1.5 py-0.5 rounded ${
        value > 0 ? "text-gray-300 bg-gray-700/50" : "text-red-400 bg-red-500/10"
      }`}
    >
      {label} {value > 0 ? `+${value}` : value}
    </span>
  );
}

/* ── Batting Breakdown Card ────────────────────────────────────────────────── */

function BattingBreakdown({ b }: { b: BattingPointsBreakdown }) {
  const lines: [string, number][] = [
    ["Runs", b.run_points],
    ["Fours Bonus", b.four_bonus],
    ["Sixes Bonus", b.six_bonus],
    ["Milestone Bonus", b.milestone_bonus],
    ["Strike Rate", b.strike_rate_bonus],
    ["Duck Penalty", b.duck_penalty],
  ];

  return (
    <BreakdownCard
      icon={<Swords className="w-4 h-4" />}
      title="Batting"
      total={b.total}
      lines={lines}
      accentColor="blue"
    />
  );
}

/* ── Bowling Breakdown Card ────────────────────────────────────────────────── */

function BowlingBreakdown({ b }: { b: BowlingPointsBreakdown }) {
  const lines: [string, number][] = [
    ["Wickets", b.wicket_points],
    ["LBW / Bowled Bonus", b.lbw_bowled_bonus],
    ["Haul Bonus", b.haul_bonus],
    ["Maiden Bonus", b.maiden_bonus],
    ["Dot Balls", b.dot_ball_points],
    ["Economy Rate", b.economy_bonus],
  ];

  return (
    <BreakdownCard
      icon={<Target className="w-4 h-4" />}
      title="Bowling"
      total={b.total}
      lines={lines}
      accentColor="purple"
    />
  );
}

/* ── Fielding Breakdown Card ───────────────────────────────────────────────── */

function FieldingBreakdown({ b }: { b: FieldingPointsBreakdown }) {
  const lines: [string, number][] = [
    ["Catches", b.catch_points],
    ["3+ Catches Bonus", b.catch_bonus],
    ["Stumpings", b.stumping_points],
    ["Run-outs", b.run_out_points],
  ];

  return (
    <BreakdownCard
      icon={<Shield className="w-4 h-4" />}
      title="Fielding"
      total={b.total}
      lines={lines}
      accentColor="amber"
    />
  );
}

/* ── Generic Breakdown Card ────────────────────────────────────────────────── */

const accentMap: Record<string, string> = {
  blue: "border-blue-500/40 text-blue-400",
  purple: "border-purple-500/40 text-purple-400",
  amber: "border-amber-500/40 text-amber-400",
};

function BreakdownCard({
  icon,
  title,
  total,
  lines,
  accentColor,
}: {
  icon: React.ReactNode;
  title: string;
  total: number;
  lines: [string, number][];
  accentColor: string;
}) {
  const accent = accentMap[accentColor] ?? accentMap.blue;

  return (
    <div className={`border rounded-lg p-3 ${accent.split(" ")[0]} bg-gray-900/40`}>
      <div className={`flex items-center gap-1.5 mb-2 font-semibold text-sm ${accent.split(" ")[1]}`}>
        {icon} {title}
        <span className="ml-auto font-bold">{total > 0 ? `+${total}` : total}</span>
      </div>
      <ul className="space-y-1">
        {lines.map(([label, value]) =>
          value !== 0 ? (
            <li key={label} className="flex justify-between text-xs">
              <span className="text-gray-400">{label}</span>
              <span className={value > 0 ? "text-emerald-400" : "text-red-400"}>
                {value > 0 ? `+${value}` : value}
              </span>
            </li>
          ) : null
        )}
        {lines.every(([, v]) => v === 0) && (
          <li className="text-xs text-gray-600">No contributions</li>
        )}
      </ul>
    </div>
  );
}
