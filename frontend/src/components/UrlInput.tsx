import { useState, useEffect } from "react";
import { Globe, Loader2, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

const ESPNCRICINFO_RE = /^https?:\/\/(?:www\.)?espncricinfo\.com\/.+\/full-scorecard/;

const PROGRESS_MESSAGES = [
  "Connecting to ESPNcricinfo...",
  "Loading scorecard page...",
  "Waiting for page to render...",
  "Parsing batting data...",
  "Parsing bowling data...",
  "Extracting fielding & dismissals...",
  "Resolving player names...",
  "Building match metadata...",
  "Almost done...",
];

interface Props {
  onScrape: (url: string) => Promise<void>;
  loading: boolean;
}

export default function UrlInput({ onScrape, loading }: Props) {
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [progressIdx, setProgressIdx] = useState(0);

  // Cycle through progress messages while loading
  useEffect(() => {
    if (!loading) {
      setProgressIdx(0);
      return;
    }
    const timer = setInterval(() => {
      setProgressIdx((prev) =>
        prev < PROGRESS_MESSAGES.length - 1 ? prev + 1 : prev
      );
    }, 4000);
    return () => clearInterval(timer);
  }, [loading]);

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

      {/* Progress indicator */}
      {loading && (
        <div className="mt-6 bg-gray-800/50 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-3">
            <Loader2 className="w-5 h-5 text-indigo-400 animate-spin shrink-0" />
            <span className="text-sm font-medium text-indigo-300">
              {PROGRESS_MESSAGES[progressIdx]}
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-1.5">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-1000"
              style={{ width: `${((progressIdx + 1) / PROGRESS_MESSAGES.length) * 100}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            This usually takes 15-30 seconds. The page needs to fully render before we can extract data.
          </p>
        </div>
      )}
    </div>
  );
}
