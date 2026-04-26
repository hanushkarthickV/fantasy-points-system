import { useState } from "react";
import { Globe, Loader2, ArrowRight } from "lucide-react";

interface Props {
  onScrape: (url: string) => Promise<void>;
  loading: boolean;
}

export default function UrlInput({ onScrape, loading }: Props) {
  const [url, setUrl] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) onScrape(url.trim());
  };

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
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.espncricinfo.com/series/..."
          required
          className="w-full px-4 py-3 rounded-xl bg-gray-800/70 border border-gray-700 
                     text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-indigo-500 focus:border-transparent transition"
        />
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
    </div>
  );
}
