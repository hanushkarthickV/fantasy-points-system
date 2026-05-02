import { useState } from "react";
import { Lock, Mail, LogIn, UserPlus } from "lucide-react";
import { login, signup } from "../services/api_v2";

interface AuthPageProps {
  onAuth: (token: string, email: string) => void;
}

export default function AuthPage({ onAuth }: AuthPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const fn = isLogin ? login : signup;
      const res = await fn(email, password);
      localStorage.setItem("fps_token", res.token);
      localStorage.setItem("fps_email", res.email);
      onAuth(res.token, res.email);
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 mb-4">
            <Lock className="w-8 h-8 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Fantasy Points System</h1>
          <p className="text-gray-400 text-sm mt-1">IPL 2026</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <div className="flex gap-1 mb-6 bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                isLogin ? "bg-indigo-500 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              Login
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                !isLogin ? "bg-indigo-500 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 font-medium mb-1 block">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  placeholder="you@example.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-400 font-medium mb-1 block">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  placeholder={isLogin ? "Your password" : "Min 6 characters"}
                  required
                  minLength={6}
                />
              </div>
            </div>

            {error && (
              <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-500/50 text-white font-medium rounded-lg text-sm flex items-center justify-center gap-2 transition-colors"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : isLogin ? (
                <>
                  <LogIn className="w-4 h-4" />
                  Login
                </>
              ) : (
                <>
                  <UserPlus className="w-4 h-4" />
                  Create Account
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
