import React, { useEffect, useState } from "react";
import { Key, LogOut, Shield, SlidersHorizontal, User, X } from "lucide-react";
import { api } from "../api/client";
import type { AuthSessionItem, AuthUser, LoginHistoryItem, UserPreferences } from "../types/workbench";
import { Badge } from "./Badge";

interface ProfileModalProps {
  user: AuthUser;
  onClose: () => void;
  onProfileUpdated: (u: AuthUser) => void;
  onPreferencesUpdated?: (prefs: UserPreferences) => void;
  onLogout: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({
  user,
  onClose,
  onProfileUpdated,
  onPreferencesUpdated,
  onLogout,
}) => {
  const [fullName, setFullName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone);
  const [department, setDepartment] = useState(user.department);
  const [title, setTitle] = useState(user.title);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AuthSessionItem[]>([]);
  const [history, setHistory] = useState<LoginHistoryItem[]>([]);

  // Workbench Preferences (Function 219)
  const [defaultTab, setDefaultTab] = useState("overview");
  const [defaultPageSize, setDefaultPageSize] = useState(30);
  const [slaLeadHours, setSlaLeadHours] = useState(6);
  const [compactMode, setCompactMode] = useState(false);
  const [prefSaving, setPrefSaving] = useState(false);
  const [prefMsg, setPrefMsg] = useState<string | null>(null);

  const loadSecurity = async () => {
    try {
      const [res, prefs] = await Promise.all([api.auth.sessions(), api.preferences()]);
      setSessions(res.sessions);
      setHistory(res.login_history);
      setDefaultTab(prefs.default_tab);
      setDefaultPageSize(prefs.default_page_size);
      setSlaLeadHours(prefs.sla_lead_hours);
      setCompactMode(Boolean(prefs.compact_mode));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to load session history");
    }
  };

  useEffect(() => {
    loadSecurity();
  }, []);

  const handleSavePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    setPrefSaving(true);
    setPrefMsg(null);
    setSaveError(null);
    try {
      const updated = await api.updatePreferences({
        default_tab: defaultTab,
        default_page_size: Number(defaultPageSize),
        sla_lead_hours: Number(slaLeadHours),
        compact_mode: compactMode,
      });
      onPreferencesUpdated?.(updated);
      setPrefMsg("Preferences applied.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to update preferences");
    } finally {
      setPrefSaving(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    setSaveError(null);
    try {
      const res = await api.auth.updateProfile({
        full_name: fullName,
        phone,
        department,
        title,
      });
      onProfileUpdated(res.user);
      setSaveMsg("Profile saved.");
      await loadSecurity();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const handleRevoke = async (sessionId: string) => {
    setSaveError(null);
    try {
      await api.auth.revokeSession(sessionId);
      await loadSecurity();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to revoke session");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-sky-950/20 dark:bg-black/50 backdrop-blur-md">
      <div className="liquid-glass w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-white/60 dark:border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-azure-600/90 dark:bg-white text-white dark:text-black border border-white/80 dark:border-transparent shadow-[0_8px_20px_rgba(24,119,242,0.28),inset_0_1px_1px_rgba(255,255,255,0.75)] dark:shadow-none flex items-center justify-center font-bold text-sm">
              {user.full_name
                .split(" ")
                .map((p) => p[0])
                .join("")
                .slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-950 dark:text-white">{user.full_name}</h3>
                <Badge variant="BLUE">{user.role}</Badge>
              </div>
              <div className="text-xs font-mono font-medium dark:font-normal text-slate-800 dark:text-zinc-400">
                {user.email} • {user.analyst_code}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-rose-500/20 hover:bg-rose-500/30 dark:hover:bg-rose-500/20 backdrop-blur-md text-rose-800 dark:text-rose-300 border border-rose-400/50 dark:border-rose-500/25 shadow-[inset_0_1px_1px_rgba(255,255,255,0.65)] dark:shadow-none text-xs font-semibold transition"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
            <button
              type="button"
              onClick={onClose}
              className="glass-pill p-2 rounded-full text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Edit Personal Profile */}
          <form onSubmit={handleSave} className="rounded-2xl bg-white/20 backdrop-blur-xl dark:bg-white/[0.04] border border-white/75 dark:border-white/12 shadow-[0_12px_28px_rgba(14,72,165,0.10),inset_0_1.5px_1.5px_rgba(255,255,255,0.88),inset_0_-1px_1px_rgba(255,255,255,0.28)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] p-4 space-y-3 text-xs">
            <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
              <User className="w-4 h-4 text-azure-600 dark:text-white" />
              <span>Personal Profile</span>
            </div>

            <label className="block space-y-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-400">Full Name</span>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
              />
            </label>
            <label className="block space-y-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-400">Job Title</span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
              />
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-400">Department</span>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
                />
              </label>
              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-400">Phone</span>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
                />
              </label>
            </div>
            <div className="flex items-center justify-between pt-1">
              <span className={saveError ? "text-rose-700 dark:text-rose-400 font-medium" : "text-emerald-700 dark:text-emerald-400 font-medium"}>
                {saveError || saveMsg || ""}
              </span>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-1.5 rounded-full bg-azure-600/95 hover:bg-azure-600 dark:bg-white text-white dark:text-black border border-white/70 dark:border-transparent shadow-[0_6px_18px_rgba(24,119,242,0.28),inset_0_1px_1px_rgba(255,255,255,0.65)] dark:shadow-none font-semibold transition"
              >
                {saving ? "Saving..." : "Save Profile"}
              </button>
            </div>
          </form>

          {/* Assigned Role & Permissions */}
          <div className="rounded-2xl bg-white/20 backdrop-blur-xl dark:bg-white/[0.04] border border-white/75 dark:border-white/12 shadow-[0_12px_28px_rgba(14,72,165,0.10),inset_0_1.5px_1.5px_rgba(255,255,255,0.88),inset_0_-1px_1px_rgba(255,255,255,0.28)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] p-4 space-y-3 text-xs">
            <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
              <Shield className="w-4 h-4 text-azure-600 dark:text-white" />
              <span>Assigned Role &amp; RBAC Permissions</span>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-white/25 backdrop-blur-md dark:bg-white/[0.05] px-3 py-2 border border-white/75 dark:border-white/12 shadow-[inset_0_1px_1px_rgba(255,255,255,0.82)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)]">
              <span className="text-slate-700 font-medium dark:font-normal dark:text-zinc-400">Active Role</span>
              <Badge variant="BLUE">{user.role}</Badge>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {user.permissions.map((perm) => (
                <Badge key={perm} variant="NEUTRAL">
                  {perm}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {/* Active Sessions & Login History */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
          <div className="rounded-2xl bg-white/20 backdrop-blur-xl dark:bg-white/[0.04] border border-white/75 dark:border-white/12 shadow-[0_12px_28px_rgba(14,72,165,0.10),inset_0_1.5px_1.5px_rgba(255,255,255,0.88),inset_0_-1px_1px_rgba(255,255,255,0.28)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] p-4 space-y-2.5">
            <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
              <Key className="w-4 h-4 text-azure-600 dark:text-white" />
              <span>Session History ({sessions.length})</span>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {sessions.map((s) => (
                <div
                  key={s.session_id}
                  className="flex items-center justify-between rounded-xl bg-white/25 backdrop-blur-md dark:bg-white/[0.05] px-3 py-2 border border-white/75 dark:border-white/12 shadow-[inset_0_1px_1px_rgba(255,255,255,0.82)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)]"
                >
                  <div>
                    <div className="font-mono font-semibold text-slate-950 dark:text-white">
                      {s.session_id} {s.session_id === user.current_session_id ? "(Current)" : ""}
                    </div>
                    <div className="ios-num text-[11px] text-slate-700 dark:text-zinc-400">
                      {s.client_ip} • {s.created_at}
                    </div>
                  </div>
                  {s.revoked ? (
                    <Badge variant="NEUTRAL">REVOKED</Badge>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleRevoke(s.session_id)}
                      className="px-2.5 py-1 rounded-full bg-rose-500/18 hover:bg-rose-500/28 border border-rose-400/45 dark:border-transparent text-rose-800 dark:text-rose-300 font-semibold transition"
                    >
                      Revoke
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-xl dark:bg-white/[0.04] border border-white/75 dark:border-white/12 shadow-[0_12px_28px_rgba(14,72,165,0.10),inset_0_1.5px_1.5px_rgba(255,255,255,0.88),inset_0_-1px_1px_rgba(255,255,255,0.28)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] p-4 space-y-2.5">
            <div className="font-semibold text-slate-900 dark:text-white">Login &amp; Security Activity</div>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {history.map((h) => (
                <div
                  key={h.log_id}
                  className="rounded-xl bg-white/25 backdrop-blur-md dark:bg-white/[0.05] px-3 py-2 border border-white/75 dark:border-white/12 shadow-[inset_0_1px_1px_rgba(255,255,255,0.82)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)]"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-slate-950 dark:text-white">{h.event_type}</span>
                    <Badge variant={h.status === "SUCCESS" ? "LOW" : "CRITICAL"}>{h.status}</Badge>
                  </div>
                  <div className="text-[11px] text-slate-700 dark:text-zinc-400 mt-0.5">{h.detail}</div>
                  <div className="ios-num text-[10.5px] text-slate-600 dark:text-zinc-500 mt-0.5">
                    {h.occurred_at} • {h.client_ip}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Workbench Preferences (Function 219) */}
        <form
          onSubmit={handleSavePrefs}
          className="rounded-2xl bg-white/20 backdrop-blur-xl dark:bg-white/[0.04] border border-white/75 dark:border-white/12 shadow-[0_12px_28px_rgba(14,72,165,0.10),inset_0_1.5px_1.5px_rgba(255,255,255,0.88),inset_0_-1px_1px_rgba(255,255,255,0.28)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.12)] p-4 space-y-3 text-xs"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
              <SlidersHorizontal className="w-4 h-4 text-azure-600 dark:text-sky-300" />
              <span>Workbench Preferences</span>
            </div>
            <span className="text-[11px] text-slate-600 dark:text-zinc-400">
              Synced per analyst across pagination &amp; SLA alerts
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <label className="block space-y-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-400">Default Tab</span>
              <select
                value={defaultTab}
                onChange={(e) => setDefaultTab(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
              >
                <option value="overview" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Overview</option>
                <option value="queue" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Triage Queue</option>
                <option value="alerts" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Alerts</option>
                <option value="customers" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Customers</option>
                <option value="accounts" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Accounts</option>
                <option value="transactions" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Transactions</option>
                <option value="governance" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">Governance &amp; Ops</option>
              </select>
            </label>

            <label className="block space-y-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-400">Rows Per Page</span>
              <select
                value={defaultPageSize}
                onChange={(e) => setDefaultPageSize(Number(e.target.value))}
                className="ios-num w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
              >
                {[15, 20, 30, 50, 100].map((sz) => (
                  <option key={sz} value={sz} className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">
                    {sz} units
                  </option>
                ))}
              </select>
            </label>

            <label className="block space-y-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-400">SLA Lead Notice (hrs)</span>
              <input
                type="number"
                min={1}
                max={48}
                value={slaLeadHours}
                onChange={(e) => setSlaLeadHours(Number(e.target.value))}
                className="ios-num w-full px-3 py-2 rounded-xl bg-white/28 backdrop-blur-md dark:bg-white/[0.06] border border-white/75 dark:border-white/15 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.84),inset_0_-1px_1px_rgba(255,255,255,0.24)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] text-slate-950 dark:text-white focus:outline-none focus:bg-white/45 dark:focus:bg-white/[0.10] focus:border-white"
              />
            </label>

            <label className="flex items-center justify-between gap-2 px-3 py-2 mt-5 rounded-xl bg-white/25 backdrop-blur-md dark:bg-white/[0.05] border border-white/75 dark:border-white/12 shadow-[inset_0_1px_1px_rgba(255,255,255,0.82)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.10)] cursor-pointer">
              <span className="font-semibold text-slate-800 dark:text-zinc-200">Compact Density</span>
              <input
                type="checkbox"
                checked={compactMode}
                onChange={(e) => setCompactMode(e.target.checked)}
                className="rounded border-slate-300 text-azure-600 focus:ring-azure-500"
              />
            </label>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-emerald-700 dark:text-emerald-400 font-medium">{prefMsg || ""}</span>
            <button
              type="submit"
              disabled={prefSaving}
              className="px-4 py-1.5 rounded-full bg-azure-600/95 hover:bg-azure-600 dark:bg-white text-white dark:text-black border border-white/70 dark:border-transparent shadow-[0_6px_18px_rgba(24,119,242,0.28),inset_0_1px_1px_rgba(255,255,255,0.65)] dark:shadow-none font-semibold transition"
            >
              {prefSaving ? "Applying..." : "Save Preferences"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
