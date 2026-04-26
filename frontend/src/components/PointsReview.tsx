import { useState } from "react";
import { Upload, ArrowRight, Loader2, ChevronDown, Swords, Target, Shield, Pencil, Save, X, Users } from "lucide-react";
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
  onEditPlayers: (edits: { original_name: string; new_name?: string; new_total_points?: number }[]) => Promise<void>;
  loading: boolean;
}

export default function PointsReview({ points, onApprove, onEditPlayers, loading }: Props) {
  const sorted = [...points.players].sort((a, b) => b.total_points - a.total_points);
  const [pendingEdits, setPendingEdits] = useState<
    Map<string, { newName?: string; newPoints?: number }>
  >(new Map());

  const hasPending = pendingEdits.size > 0;

  const handleEdit = (origName: string, field: "name" | "points", value: string) => {
    setPendingEdits((prev) => {
      const next = new Map(prev);
      const existing = next.get(origName) ?? {};
      if (field === "name") existing.newName = value;
      else existing.newPoints = value === "" ? undefined : parseInt(value, 10);
      next.set(origName, existing);
      return next;
    });
  };

  const cancelEdits = () => setPendingEdits(new Map());

  const saveEdits = async () => {
    const edits = Array.from(pendingEdits.entries()).map(([origName, e]) => ({
      original_name: origName,
      new_name: e.newName,
      new_total_points: e.newPoints,
    }));
    await onEditPlayers(edits);
    setPendingEdits(new Map());
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-white mb-1">Fantasy Points Calculated</h2>
        <p className="text-gray-400 text-sm">
          Match ID: {points.match_id} &middot; {points.players.length} players scored
          &middot; Click a row to see breakdown &middot; Click <Pencil className="w-3 h-3 inline" /> to edit
        </p>
      </div>

      {/* Players Accordion */}
      <div className="space-y-2">
        {sorted.map((p, i) => (
          <PlayerAccordion
            key={p.name}
            player={p}
            rank={i + 1}
            pendingEdit={pendingEdits.get(p.name)}
            onEdit={(field, val) => handleEdit(p.name, field, val)}
          />
        ))}
      </div>

      {/* Save edits bar */}
      {hasPending && (
        <div className="flex items-center gap-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-4">
          <Pencil className="w-5 h-5 text-indigo-400 shrink-0" />
          <span className="text-indigo-200 text-sm flex-1">
            {pendingEdits.size} player(s) edited. Save changes before updating the sheet.
          </span>
          <button
            onClick={cancelEdits}
            className="px-3 py-1.5 rounded-lg text-sm text-gray-300 hover:bg-gray-700 transition"
          >
            <X className="w-4 h-4 inline mr-1" />Cancel
          </button>
          <button
            onClick={saveEdits}
            disabled={loading}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition disabled:opacity-50"
          >
            <Save className="w-4 h-4 inline mr-1" />Save Edits
          </button>
        </div>
      )}

      {/* Approve Button */}
      <button
        onClick={onApprove}
        disabled={loading || hasPending}
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

function PlayerAccordion({
  player,
  rank,
  pendingEdit,
  onEdit,
}: {
  player: PlayerPoints;
  rank: number;
  pendingEdit?: { newName?: string; newPoints?: number };
  onEdit: (field: "name" | "points", value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);

  const batTotal = player.batting?.total ?? 0;
  const bowlTotal = player.bowling?.total ?? 0;
  const fieldTotal = player.fielding?.total ?? 0;

  const displayPoints = pendingEdit?.newPoints ?? player.total_points;
  const displayName = pendingEdit?.newName ?? player.name;

  const totalColor =
    displayPoints >= 50
      ? "bg-emerald-500/20 text-emerald-300"
      : displayPoints >= 0
      ? "bg-gray-700 text-white"
      : "bg-red-500/20 text-red-300";

  return (
    <div className={`bg-gray-800/50 border rounded-xl overflow-hidden transition-all ${pendingEdit ? "border-indigo-500/50" : "border-gray-700"}`}>
      {/* Header Row — always visible */}
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="text-gray-500 font-mono text-xs w-6 text-right shrink-0">{rank}</span>

        {editing ? (
          <input
            value={displayName}
            onChange={(e) => onEdit("name", e.target.value)}
            className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <button
            onClick={() => setOpen(!open)}
            className="font-medium text-white truncate flex-1 text-left hover:text-indigo-300 transition"
          >
            {displayName}
          </button>
        )}

        <span className="text-gray-500 text-xs hidden sm:inline">{player.team}</span>

        {/* Playing XI badge */}
        {player.playing_xi_bonus > 0 && (
          <span className="hidden sm:inline text-xs px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300">
            <Users className="w-3 h-3 inline mr-0.5" />+{player.playing_xi_bonus}
          </span>
        )}

        <div className="flex items-center gap-3 ml-auto shrink-0">
          <CategoryPill label="BAT" value={batTotal} />
          <CategoryPill label="BOWL" value={bowlTotal} />
          <CategoryPill label="FLD" value={fieldTotal} />

          {editing ? (
            <input
              type="number"
              value={displayPoints}
              onChange={(e) => onEdit("points", e.target.value)}
              className="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-white text-sm font-bold text-center focus:outline-none focus:ring-1 focus:ring-indigo-500"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className={`inline-block px-2.5 py-0.5 rounded-md font-bold text-sm ${totalColor}`}>
              {displayPoints}
            </span>
          )}

          <button
            onClick={(e) => { e.stopPropagation(); setEditing(!editing); }}
            className={`p-1 rounded transition ${editing ? "text-indigo-400 bg-indigo-500/20" : "text-gray-500 hover:text-gray-300"}`}
            title={editing ? "Done editing" : "Edit player"}
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>

          <button onClick={() => setOpen(!open)}>
            <ChevronDown
              className={`w-4 h-4 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Expanded Breakdown */}
      {open && (
        <div className="border-t border-gray-700 px-4 py-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {player.batting && <BattingBreakdown b={player.batting} />}
          {player.bowling && <BowlingBreakdown b={player.bowling} />}
          {player.fielding && <FieldingBreakdown b={player.fielding} />}
          {player.playing_xi_bonus > 0 && (
            <div className="border border-cyan-500/40 rounded-lg p-3 bg-gray-900/40">
              <div className="flex items-center gap-1.5 mb-2 font-semibold text-sm text-cyan-400">
                <Users className="w-4 h-4" /> Playing XI
                <span className="ml-auto font-bold">+{player.playing_xi_bonus}</span>
              </div>
              <p className="text-xs text-gray-400">Bonus for being in the playing squad</p>
            </div>
          )}
          {!player.batting && !player.bowling && !player.fielding && player.playing_xi_bonus === 0 && (
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
