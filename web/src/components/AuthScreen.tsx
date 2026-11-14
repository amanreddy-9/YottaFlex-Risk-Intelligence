import React, { useState } from "react";
import { KeyRound, Lock, Mail, Moon, ShieldCheck, Sun, UserCheck } from "lucide-react";
import { api, setStoredToken } from "../api/client";
import type { AuthUser } from "../types/workbench";

interface AuthScreenProps {
  darkMode: boolean;
  onToggleTheme: () => void;
  onAuthenticated: (user: AuthUser) => void;
}

const ROLE_PRESETS = [
  {
    label: "Operations Analyst",
    email: "analyst@yottaflex.com",
    role: "OPS_ANALYST",
    desc: "Triage alerts, investigate cases & submit notes",
  },
  {
    label: "Risk / Compliance Reviewer",
    email: "reviewer@yottaflex.com",
    role: "RISK_REVIEWER",
    desc: "Review escalations, approve dispositions & file SAR",
  },
  {
    label: "System Administrator",
    email: "admin@yottaflex.com",
    role: "SYSTEM_ADMIN",
    desc: "Manage RBAC users, rules, synthetic data & audit logs",
  },
];

export const AuthScreen: React.FC<AuthScreenProps> = ({ darkMode, onToggleTheme, onAuthenticated }) => {
  const [mode, setMode] = useState<"login" | "forgot" | "reset">("login");
  const [email, setEmail] = useState("analyst@yottaflex.com");
  const [password, setPassword] = useState("YottaFlex#2026");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [issuedCodeHint, setIssuedCodeHint] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.auth.login(email, password);
      setStoredToken(res.token);
      onAuthenticated(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const res = await api.auth.forgotPassword(email);
      setIssuedCodeHint(res.demo_reset_code);
      setResetCode(res.demo_reset_code);
      setInfo(`15-minute reset token generated (${res.reset_id}). Enter your new password below.`);
      setMode("reset");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.auth.resetPassword({ email, reset_code: resetCode, new_password: newPassword });
      setPassword(newPassword);
      setInfo("Password updated cleanly. Sign in with your new password.");
      setMode("login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="yf-backdrop-light relative min-h-screen flex items-center justify-center p-6 overflow-hidden">
      {/* Background Watermarks (Image 1 & 2 style) */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none overflow-hidden">
        <img
          src="/yottaflex-logo.webp"
          alt=""
          className="absolute right-[6%] bottom-[8%] w-[520px] max-w-[54vw] opacity-[0.26] brightness-[0.82] contrast-[1.14] saturate-[1.18] dark:opacity-[0.22] dark:brightness-125 dark:contrast-100 dark:saturate-150 select-none drop-shadow-[0_14px_40px_rgba(10,40,110,0.35)] dark:drop-shadow-[0_12px_36px_rgba(22,90,220,0.32)]"
        />
        <div className="hidden md:block absolute left-10 bottom-8 text-[96px] font-bold tracking-tighter text-white/35 dark:text-azure-400/[0.10] select-none leading-none">
          Sign In
        </div>
      </div>

      <button
        type="button"
        onClick={onToggleTheme}
        className="fixed top-5 right-6 z-20 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-white/75 dark:bg-zinc-900 border border-white/90 dark:border-white/15 text-xs font-semibold text-slate-800 dark:text-white shadow-sm backdrop-blur-md"
      >
        {darkMode ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5 text-azure-600" />}
        <span>{darkMode ? "Light" : "Dark"}</span>
      </button>

      <div className="relative z-10 w-full max-w-4xl grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch">
        {/* Left Role Selector Card */}
        <div className="md:col-span-5 liquid-glass-hero rounded-3xl p-6 text-white flex flex-col justify-between">
          <div>
            <a
              href="https://stg.yottaflex.ai"
              target="_blank"
              rel="noopener noreferrer"
              title="https://stg.yottaflex.ai"
              className="group inline-flex items-center gap-3 cursor-pointer"
            >
              <div className="w-11 h-11 rounded-2xl bg-white/90 dark:bg-zinc-900 p-2 shadow-sm flex items-center justify-center transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:-translate-y-1.5 group-hover:scale-110 group-hover:shadow-lg">
                <img
                  src="/yottaflex-logo.webp"
                  alt="YottaFlex Logo"
                  className="w-full h-full object-contain dark:brightness-0 dark:invert"
                />
              </div>
              <div>
                <div className="text-base font-bold tracking-tight">YottaFlex</div>
                <div className="text-xs text-white/80">AML Risk &amp; Compliance OS</div>
              </div>
            </a>

            <h1 className="mt-6 text-2xl font-bold tracking-tight leading-snug">
              Role-Based Transaction &amp; Account Triage
            </h1>
            <p className="mt-2 text-xs text-white/80 leading-relaxed">
              Sign in with PBKDF2-verified credentials or select a pre-provisioned institutional role to test permissions,
              audit trails, and case workflows.
            </p>
          </div>

          <div className="mt-6 space-y-2">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-white/75">
              Quick-Fill Institutional Role
            </div>
            {ROLE_PRESETS.map((p) => {
              const selected = email.toLowerCase() === p.email.toLowerCase();
              return (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => {
                    setEmail(p.email);
                    setPassword("YottaFlex#2026");
                    setMode("login");
                    setError(null);
                  }}
                  className={`w-full text-left rounded-2xl p-3 border transition ${
                    selected
                      ? "bg-white/25 border-white/75 shadow-sm"
                      : "bg-white/10 border-white/20 hover:bg-white/18"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold">{p.label}</span>
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-black/20">{p.role}</span>
                  </div>
                  <div className="text-[11px] text-white/80 mt-0.5">{p.desc}</div>
                  <div className="mt-1.5 font-mono text-[10.5px] text-white/95 bg-black/20 rounded-lg px-2 py-1 flex flex-wrap justify-between gap-1">
                    <span>{p.email}</span>
                    <span>Pass: YottaFlex#2026</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Liquid Glass Auth Form */}
        <div className="md:col-span-7 liquid-glass rounded-3xl p-7 flex flex-col justify-center">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-xl font-bold text-slate-950 dark:text-white">
                {mode === "login"
                  ? "Secure Sign In"
                  : mode === "forgot"
                  ? "Reset Forgotten Password"
                  : "Confirm Password Reset"}
              </h2>
              <p className="text-xs text-slate-600 dark:text-zinc-400 mt-0.5">
                {mode === "login"
                  ? "Authenticated sessions are logged to the immutable security ledger."
                  : "Verify identity and issue a new PBKDF2 salted password hash."}
              </p>
            </div>
            <ShieldCheck className="w-6 h-6 text-azure-600 dark:text-white" />
          </div>

          {error && (
            <div className="mb-4 rounded-xl bg-rose-500/12 border border-rose-500/30 px-3.5 py-2.5 text-xs font-medium text-rose-700 dark:text-rose-300">
              {error}
            </div>
          )}
          {info && (
            <div className="mb-4 rounded-xl bg-emerald-500/12 border border-emerald-500/30 px-3.5 py-2.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
              {info}
            </div>
          )}

          {mode === "login" && (
            <form onSubmit={handleLogin} className="space-y-4 text-xs">
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Work Email</span>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl glass-pill text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-azure-500/40"
                  />
                </div>
              </label>

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Password</span>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl glass-pill text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-azure-500/40"
                  />
                </div>
              </label>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setMode("forgot");
                    setError(null);
                    setInfo(null);
                  }}
                  className="text-azure-700 dark:text-zinc-300 font-semibold hover:underline"
                >
                  Forgot password?
                </button>
              </div>

              <div className="rounded-2xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/75 dark:border-white/15 px-3.5 py-2.5 text-[11px] font-mono space-y-1">
                <div className="font-sans font-semibold text-slate-700 dark:text-zinc-300 text-[10.5px] uppercase tracking-wider">
                  Verifier Sample Credentials
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 text-slate-800 dark:text-zinc-200">
                  <span>
                    Email: <strong className="text-azure-700 dark:text-white">{email || "analyst@yottaflex.com"}</strong>
                  </span>
                  <span>
                    Password: <strong className="text-azure-700 dark:text-white">YottaFlex#2026</strong>
                  </span>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-full bg-azure-600 hover:bg-azure-700 dark:bg-white dark:hover:bg-zinc-200 text-white dark:text-black font-semibold text-xs shadow-sm transition inline-flex items-center justify-center gap-2"
              >
                <UserCheck className="w-4 h-4" />
                <span>{loading ? "Authenticating..." : "Sign In to Workbench"}</span>
              </button>
            </form>
          )}

          {mode === "forgot" && (
            <form onSubmit={handleRequestReset} className="space-y-4 text-xs">
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Registered Account Email</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl glass-pill text-slate-900 dark:text-white"
                />
              </label>
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setMode("login")}
                  className="glass-pill px-4 py-2 rounded-full font-semibold hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                >
                  Back to Sign In
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2.5 rounded-full bg-azure-600 dark:bg-white text-white dark:text-black font-semibold inline-flex items-center gap-1.5"
                >
                  <KeyRound className="w-3.5 h-3.5" /> Issue Reset Code
                </button>
              </div>
            </form>
          )}

          {mode === "reset" && (
            <form onSubmit={handleConfirmReset} className="space-y-4 text-xs">
              {issuedCodeHint && (
                <div className="rounded-xl bg-azure-500/10 border border-azure-500/25 px-3 py-2 font-mono text-[11px] text-azure-700 dark:text-zinc-200">
                  Demo Reset Code: <strong>{issuedCodeHint}</strong>
                </div>
              )}
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">6-Digit Reset Code</span>
                <input
                  type="text"
                  required
                  value={resetCode}
                  onChange={(e) => setResetCode(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/80 dark:bg-zinc-900 border border-white dark:border-white/15 font-mono text-slate-900 dark:text-white"
                />
              </label>
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">New Password (min 8 chars)</span>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl glass-pill text-slate-900 dark:text-white"
                />
              </label>
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setMode("login")}
                  className="glass-pill px-4 py-2 rounded-full font-semibold hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2.5 rounded-full bg-azure-600 dark:bg-white text-white dark:text-black font-semibold"
                >
                  Save New Password
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
