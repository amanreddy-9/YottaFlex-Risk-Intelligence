import React, { useEffect, useState } from "react";
import {
  Briefcase,
  CheckCircle2,
  Key,
  Laptop,
  LogOut,
  Mail,
  Phone,
  Shield,
  SlidersHorizontal,
  User,
  X,
} from "lucide-react";
import { api } from "../api/client";
import type { AuthSessionItem, AuthUser, LoginHistoryItem, UserPreferences } from "../types/workbench";
import { Badge } from "./Badge";
import { LiquidGlassSegmented } from "./LiquidGlassSurface";

type ProfileTab = "profile" | "permissions" | "sessions" | "preferences";

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
  const [activeTab, setActiveTab] = useState<ProfileTab>("profile");
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
      setPrefMsg("Preferences saved successfully.");
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
      setSaveMsg("Profile details updated.");
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-sky-950/25 dark:bg-black/60 backdrop-blur-md">
      <div className="liquid-glass w-full max-w-3xl max-h-[92vh] overflow-y-auto rounded-3xl p-6 sm:p-7 space-y-5 shadow-[0_24px_64px_rgba(0,0,0,0.30)]">
        {/* Top Header Card */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-white/50 dark:border-white/10">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-azure-500 to-azure-700 text-white font-bold text-base flex items-center justify-center shadow-[0_8px_20px_rgba(24,119,242,0.35),inset_0_1px_1px_rgba(255,255,255,0.75)] select-none">
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
              <div className="text-xs font-mono text-slate-600 dark:text-zinc-400 mt-0.5">
                {user.email} • <span className="font-semibold text-slate-800 dark:text-zinc-300">{user.analyst_code}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-rose-500/15 hover:bg-rose-500/25 text-rose-700 dark:text-rose-300 border border-rose-400/35 dark:border-rose-500/20 text-xs font-semibold transition"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
            <button
              type="button"
              onClick={onClose}
              className="glass-pill p-2 rounded-full text-slate-700 dark:text-zinc-300 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
              title="Close Profile"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Liquid Glass Segmented Slider Sub-Navigation */}
        <div className="w-full flex justify-center">
          <LiquidGlassSegmented<ProfileTab>
            value={activeTab}
            onChange={setActiveTab}
            options={[
              {
                value: "profile",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <User className="w-3.5 h-3.5" />
                    <span>Personal Profile</span>
                  </span>
                ),
              },
              {
                value: "permissions",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <Shield className="w-3.5 h-3.5 text-azure-600 dark:text-sky-400" />
                    <span>Role &amp; RBAC</span>
                  </span>
                ),
              },
              {
                value: "sessions",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <Key className="w-3.5 h-3.5 text-amber-500" />
                    <span>Sessions &amp; Activity ({sessions.length})</span>
                  </span>
                ),
              },
              {
                value: "preferences",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-purple-500" />
                    <span>Preferences</span>
                  </span>
                ),
              },
            ]}
          />
        </div>

        {/* Tab 1: Personal Profile */}
        {activeTab === "profile" && (
          <form onSubmit={handleSave} className="p-5 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-4 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-white/40 dark:border-white/10">
              <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white text-sm">
                <User className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                <span>Identity &amp; Operational Attributes</span>
              </div>
              <span className="text-[11px] text-slate-500 dark:text-zinc-400">Analyst credentials &amp; contact routing</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-slate-400" /> Full Name
                </span>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <Briefcase className="w-3.5 h-3.5 text-slate-400" /> Job Title
                </span>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-slate-400" /> Department
                </span>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-slate-400" /> Direct Phone
                </span>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                />
              </label>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/30 dark:border-white/10">
              <span className={saveError ? "text-rose-600 dark:text-rose-400 font-semibold text-xs" : "text-emerald-600 dark:text-emerald-400 font-semibold text-xs flex items-center gap-1"}>
                {saveMsg && <CheckCircle2 className="w-3.5 h-3.5" />}
                {saveError || saveMsg || ""}
              </span>
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 rounded-full bg-azure-600 hover:bg-azure-700 text-white font-semibold shadow-sm transition disabled:opacity-50"
              >
                {saving ? "Saving Changes..." : "Save Profile Details"}
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: Assigned Role & RBAC Permissions */}
        {activeTab === "permissions" && (
          <div className="p-5 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-4 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-white/40 dark:border-white/10">
              <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white text-sm">
                <Shield className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                <span>Assigned Role &amp; Access Controls</span>
              </div>
              <Badge variant="BLUE">{user.role}</Badge>
            </div>

            <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/50 dark:border-white/10 space-y-1.5">
              <div className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span>Enterprise Authorization Tier:</span>
                <span className="font-mono text-azure-600 dark:text-sky-400">{user.role}</span>
              </div>
              <p className="text-[11.5px] text-slate-600 dark:text-zinc-300 leading-relaxed">
                {user.role === "SYSTEM_ADMIN"
                  ? "Full administrative governance across network intelligence, transaction execution, risk rules authoring, user orchestration, and compliance audit reporting."
                  : "Role-based operating credentials configured per enterprise compliance policies."}
              </p>
            </div>

            <div className="space-y-2 pt-1">
              <div className="text-[11px] uppercase tracking-wider font-bold text-slate-500 dark:text-zinc-400">
                Granted RBAC Operational Permissions ({user.permissions.length})
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                {user.permissions.map((perm) => (
                  <span
                    key={perm}
                    className="glass-pill px-3 py-1.5 rounded-full font-mono text-[11px] font-semibold text-slate-800 dark:text-zinc-200"
                  >
                    {perm}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Active Sessions & Login Activity */}
        {activeTab === "sessions" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {/* Active Sessions */}
            <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-white/40 dark:border-white/10">
                <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                  <Key className="w-4 h-4 text-amber-500" />
                  <span>Session History ({sessions.length})</span>
                </div>
                <span className="text-[10px] text-slate-400">Authenticated devices</span>
              </div>

              <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                {sessions.map((s) => (
                  <div
                    key={s.session_id}
                    className="p-3 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 flex items-center justify-between gap-2"
                  >
                    <div>
                      <div className="font-mono font-bold text-slate-950 dark:text-white flex items-center gap-1.5">
                        <Laptop className="w-3.5 h-3.5 text-slate-400" />
                        <span>{s.session_id}</span>
                        {s.session_id === user.current_session_id && (
                          <span className="px-1.5 py-0.5 rounded text-[9.5px] font-bold bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                            Current
                          </span>
                        )}
                      </div>
                      <div className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-400 mt-0.5">
                        {s.client_ip} • {s.created_at}
                      </div>
                    </div>
                    {s.revoked ? (
                      <Badge variant="NEUTRAL">REVOKED</Badge>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleRevoke(s.session_id)}
                        className="px-2.5 py-1 rounded-full bg-rose-500/15 hover:bg-rose-500/25 border border-rose-400/35 text-rose-700 dark:text-rose-300 font-semibold text-[11px] transition shrink-0"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Login & Security Activity */}
            <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-white/40 dark:border-white/10">
                <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                  <Laptop className="w-4 h-4 text-sky-500" />
                  <span>Security Audit Trail</span>
                </div>
                <span className="text-[10px] text-slate-400">{history.length} events logged</span>
              </div>

              <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                {history.map((h) => (
                  <div
                    key={h.log_id}
                    className="p-3 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-950 dark:text-white">{h.event_type}</span>
                      <Badge variant={h.status === "SUCCESS" ? "LOW" : "CRITICAL"}>{h.status}</Badge>
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-zinc-300">{h.detail}</div>
                    <div className="ios-num text-[10px] text-slate-400 dark:text-zinc-500">
                      {h.occurred_at} • {h.client_ip}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Workbench Preferences */}
        {activeTab === "preferences" && (
          <form
            onSubmit={handleSavePrefs}
            className="p-5 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-4 text-xs"
          >
            <div className="flex items-center justify-between pb-2 border-b border-white/40 dark:border-white/10">
              <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white text-sm">
                <SlidersHorizontal className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <span>Analyst Workbench Preferences</span>
              </div>
              <span className="text-[11px] text-slate-500 dark:text-zinc-400">Synced across session restarts</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Default Landing View</span>
                <select
                  value={defaultTab}
                  onChange={(e) => setDefaultTab(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
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

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Pagination Default Rows</span>
                <select
                  value={defaultPageSize}
                  onChange={(e) => setDefaultPageSize(Number(e.target.value))}
                  className="ios-num w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                >
                  {[15, 20, 30, 50, 100].map((sz) => (
                    <option key={sz} value={sz} className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">
                      {sz} items per page
                    </option>
                  ))}
                </select>
              </label>

              <label className="block space-y-1.5">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">SLA Lead Notice Window (Hours)</span>
                <input
                  type="number"
                  min={1}
                  max={48}
                  value={slaLeadHours}
                  onChange={(e) => setSlaLeadHours(Number(e.target.value))}
                  className="ios-num w-full px-3.5 py-2.5 rounded-xl bg-white/70 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 text-slate-950 dark:text-white font-medium focus:outline-none focus:border-azure-500 transition"
                />
              </label>

              <label className="flex items-center justify-between gap-3 px-4 py-2.5 mt-5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/15 cursor-pointer">
                <div>
                  <div className="font-bold text-slate-900 dark:text-white">Compact Table Density</div>
                  <div className="text-[10.5px] text-slate-500 dark:text-zinc-400">Reduce table row padding for high-density analysis</div>
                </div>
                <input
                  type="checkbox"
                  checked={compactMode}
                  onChange={(e) => setCompactMode(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-azure-600 focus:ring-azure-500 cursor-pointer"
                />
              </label>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/30 dark:border-white/10">
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold text-xs flex items-center gap-1">
                {prefMsg && <CheckCircle2 className="w-3.5 h-3.5" />}
                {prefMsg || ""}
              </span>
              <button
                type="submit"
                disabled={prefSaving}
                className="px-5 py-2 rounded-full bg-azure-600 hover:bg-azure-700 text-white font-semibold shadow-sm transition disabled:opacity-50"
              >
                {prefSaving ? "Applying..." : "Save Preferences"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
