import { useState, useEffect, useRef } from "react";
import { Globe, Loader2, ArrowRight, AlertCircle, CheckCircle2, Clock } from "lucide-react";

const ESPNCRICINFO_RE = /^https?:\/\/(?:www\.)?espncricinfo\.com\/.+\/full-scorecard/;

// Ordered steps with their target percentage
const STEP_ORDER = [
  "init", "browser_launch", "page_load", "waiting_render",
  "extracting_html", "parse_batting", "parse_innings",
  "resolve_names", "complete",
];
const STEP_PROGRESS: Record<string, number> = {
  init: 5,  browser_launch: 12, page_load: 30, waiting_render: 50,
  extracting_html: 65, parse_batting: 75, parse_innings: 85,
  resolve_names: 93, complete: 100, retry: 25,
};

// Sub-messages shown during long waits for specific steps
const WAIT_HINTS: Record<string, string[]> = {
  "": [
    "Establishing connection to server...",
    "Warming up the scraping engine...",
  ],
  browser_launch: [
    "Starting headless Chrome — this takes 15-30s on free tier...",
    "Chrome is loading required libraries...",
    "Almost ready to navigate to the scorecard...",
    "Free-tier cold start can be slow — hang tight!",
  ],
  page_load: [
    "Waiting for ESPNcricinfo to respond...",
    "Loading the full scorecard page...",
    "The page is large — still downloading...",
  ],
  waiting_render: [
    "JavaScript is rendering the scorecard tables...",
    "Waiting for dynamic content to appear...",
  ],
};

interface Props {
  onScrape: (url: string) => Promise<void>;
  loading: boolean;
  progressStep?: string;
  progressMessage?: string;
}

export default function UrlInput({ onScrape, loading, progressStep, progressMessage }: Props) {
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Smooth animation state
  const [displayPct, setDisplayPct] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [hintIdx, setHintIdx] = useState(0);
  const startRef = useRef<number>(0);
  const lastStepRef = useRef<string>("");

  // Reset on loading start/stop
  useEffect(() => {
    if (loading) {
      startRef.current = Date.now();
      setDisplayPct(0);
      setElapsed(0);
      setHintIdx(0);
      lastStepRef.current = "";
    } else {
      setDisplayPct(0);
      setElapsed(0);
    }
  }, [loading]);

  // Smooth progress animation — tick every 800ms
  useEffect(() => {
    if (!loading) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));

      const targetPct = progressStep ? (STEP_PROGRESS[progressStep] ?? 50) : 2;
      // Find the next step's pct to use as ceiling for interpolation
      const curIdx = STEP_ORDER.indexOf(progressStep || "");
      const nextPct = curIdx >= 0 && curIdx < STEP_ORDER.length - 1
        ? STEP_PROGRESS[STEP_ORDER[curIdx + 1]]
        : targetPct + 10;
      const ceiling = Math.min(nextPct - 2, 98); // don't exceed next step

      setDisplayPct((prev) => {
        if (prev < targetPct) {
          // Jump quickly to the step's base percentage
          return targetPct;
        }
        // Slowly creep toward the ceiling while waiting
        if (prev < ceiling) {
          return Math.min(prev + 0.5, ceiling);
        }
        return prev;
      });
    }, 800);
    return () => clearInterval(timer);
  }, [loading, progressStep]);

  // Cycle wait hints every 5s when stuck on same step
  useEffect(() => {
    if (!loading) return;
    if (progressStep !== lastStepRef.current) {
      lastStepRef.current = progressStep || "";
      setHintIdx(0);
    }
    const timer = setInterval(() => {
      setHintIdx((i) => i + 1);
    }, 5000);
    return () => clearInterval(timer);
  }, [loading, progressStep]);

  const validate = (value: string): string | null => {
    if (!value.trim()) return null;
    if (!ESPNCRICINFO_RE.test(value.trim())) {
      return "URL must be a valid ESPNcricinfo full-scorecard link (e.g. https://www.espncricinfo.com/series/.../full-scorecard)";
    }
    return null;
  };

  const handleChange = (value: string) => {
    setUrl(value);
    if (validationError) setValidationError(validate(value));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate(url);
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);
    onScrape(url.trim());
  };

  const isValid = url.trim() && !validate(url);

  // Pick the display message: SSE message first, then wait hints
  const hints = WAIT_HINTS[progressStep || ""] || [];
  const hintText = hints.length > 0 ? hints[hintIdx % hints.length] : null;
  const displayMessage = progressMessage || "Connecting to backend...";
  const roundedPct = Math.round(displayPct);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 mb-4">
          <Globe className="w-8 h-8 text-indigo-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          Scrape Match Scorecard
        </h2>
        <p className="text-gray-400">
          Paste an ESPNcricinfo full-scorecard URL to begin
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <div className="relative">
            <input
              type="url"
              value={url}
              onChange={(e) => handleChange(e.target.value)}
              onBlur={() => setValidationError(validate(url))}
              placeholder="https://www.espncricinfo.com/series/.../full-scorecard"
              required
              disabled={loading}
              className={`w-full px-4 py-3 rounded-xl bg-gray-800/70 border 
                         text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 
                         focus:border-transparent transition pr-10
                         ${validationError ? "border-red-500 focus:ring-red-500" : isValid ? "border-emerald-500/50 focus:ring-emerald-500" : "border-gray-700 focus:ring-indigo-500"}`}
            />
            {isValid && !loading && (
              <CheckCircle2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-emerald-400" />
            )}
          </div>
          {validationError && (
            <div className="flex items-center gap-1.5 mt-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl 
                     bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed 
                     text-white font-semibold transition"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Scraping scorecard...
            </>
          ) : (
            <>
              Scrape Scorecard
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </form>

      {/* Live progress indicator powered by SSE + smooth animation */}
      {loading && (
        <div className="mt-6 bg-gray-800/50 border border-gray-700 rounded-xl p-4 space-y-3">
          {/* Primary status */}
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-indigo-400 animate-spin shrink-0" />
            <span className="text-sm font-medium text-indigo-300">
              {displayMessage}
            </span>
          </div>

          {/* Context hint during long waits */}
          {hintText && (
            <p className="text-xs text-gray-400 pl-8 transition-opacity duration-500">
              {hintText}
            </p>
          )}

          {/* Progress bar */}
          <div className="w-full bg-gray-700 rounded-full h-1.5">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${roundedPct}%` }}
            />
          </div>

          {/* Footer: elapsed time + percentage */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              <span className="tabular-nums">{mm}:{ss} elapsed</span>
            </div>
            <span className="text-xs text-gray-500 tabular-nums">{roundedPct}%</span>
          </div>
        </div>
      )}
    </div>
  );
}
