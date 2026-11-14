import React, { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import {
  ArrowLeftRight,
  BarChart3,
  Bell,
  CreditCard,
  FolderSearch,
  GitFork,
  Keyboard,
  Layers,
  LayoutDashboard,
  Moon,
  Scale,
  Search,
  ShieldAlert,
  Sun,
  UserCircle2,
  Users,
  X,
} from "lucide-react";
import { api, getStoredToken, setStoredToken } from "./api/client";
import { AccountsView } from "./components/AccountsView";
import { AlertsView, type AlertFiltersState } from "./components/AlertsView";
import { AuthScreen } from "./components/AuthScreen";
import { CustomersView } from "./components/CustomersView";
import { DashboardView } from "./components/DashboardView";
import { DossierView } from "./components/DossierView";
import { EvaluationView } from "./components/EvaluationView";
import { Footer } from "./components/Footer";
import { GlobalSearchModal } from "./components/GlobalSearchModal";
import { GovernanceView } from "./components/GovernanceView";
import { NetworkIntelligenceView } from "./components/NetworkIntelligenceView";
import type { NavItem } from "./components/LiquidGlassNav";
import { NotificationBellButton, NotificationWindowPanel, type AnchorRect } from "./components/NotificationWidget";
import { OverviewSidebar } from "./components/OverviewSidebar";
import { ProfileModal } from "./components/ProfileModal";
import { QuarantineView } from "./components/QuarantineView";
import { QueueView } from "./components/QueueView";
import { TransactionsView, type TransactionFiltersState } from "./components/TransactionsView";
import { YottaBotWidget, type BotAction } from "./components/YottaBotWidget";
import type {
  AccountDetail,
  AccountListItem,
  AlertDetail,
  AlertListItem,
  AuthUser,
  CaseDossier,
  CaseListItem,
  CustomerListItem,
  CustomerProfile,
  DashboardData,
  EvaluationData,
  NotificationItem,
  OverviewData,
  QuarantineData,
  RiskRuleItem,
  RiskScoringOverview,
  TransactionDetail,
  TransactionItem,
  UserPreferences,
} from "./types/workbench";

type Tab =
  | "overview"
  | "queue"
  | "customers"
  | "accounts"
  | "transactions"
  | "network"
  | "alerts"
  | "dossier"
  | "quarantine"
  | "evaluation"
  | "governance";

export const App: React.FC = () => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showSpotlight, setShowSpotlight] = useState(false);
  const [showNotifs, setShowNotifs] = useState(false);
  const [notifAnchor, setNotifAnchor] = useState<AnchorRect>({ top: 18, right: 180 });
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const [tab, setTab] = useState<Tab>("overview");
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem("yottaflex_theme");
    return saved !== "light";
  });

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashFilters, setDashFilters] = useState({
    period: "ALL",
    start_date: "",
    end_date: "",
    risk_level: "ALL",
    txn_type: "ALL",
    status: "ALL",
  });

  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [totalCases, setTotalCases] = useState(0);
  const [dossier, setDossier] = useState<CaseDossier | null>(null);
  const [quarantine, setQuarantine] = useState<QuarantineData | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [rules, setRules] = useState<RiskRuleItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Queue filters & pagination (30 default)
  const [queuePage, setQueuePage] = useState(0);
  const [queuePageSize, setQueuePageSize] = useState(30);
  const [sort, setSort] = useState<"priority" | "fifo">("priority");
  const [tier, setTier] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [linkage, setLinkage] = useState("ALL");
  const [search, setSearch] = useState("");
  const [queueAssignee, setQueueAssignee] = useState("ALL");
  const [queueSla, setQueueSla] = useState("ALL");
  const [queueMinExp, setQueueMinExp] = useState("");
  const [queueMaxExp, setQueueMaxExp] = useState("");
  const [queueStartDate, setQueueStartDate] = useState("");
  const [queueEndDate, setQueueEndDate] = useState("");

  // Customer directory & 360 profile (30 default)
  const [custPageSize, setCustPageSize] = useState(30);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [totalCustomers, setTotalCustomers] = useState(0);
  const [custPage, setCustPage] = useState(0);
  const [custSearch, setCustSearch] = useState("");
  const [custKyc, setCustKyc] = useState("ALL");
  const [custRisk, setCustRisk] = useState("ALL");
  const [custAcctStatus, setCustAcctStatus] = useState("ALL");
  const [custMultiSuspicious, setCustMultiSuspicious] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerProfile | null>(null);

  // Account management & 360 detail (30 default)
  const [acctPageSize, setAcctPageSize] = useState(30);
  const [accounts, setAccounts] = useState<AccountListItem[]>([]);
  const [totalAccounts, setTotalAccounts] = useState(0);
  const [acctPage, setAcctPage] = useState(0);
  const [acctSearch, setAcctSearch] = useState("");
  const [acctStatus, setAcctStatus] = useState("ALL");
  const [acctDormant, setAcctDormant] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<AccountDetail | null>(null);

  // Transaction monitoring & risk scoring (30 default)
  const [txnPageSize, setTxnPageSize] = useState(30);
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [txnPage, setTxnPage] = useState(0);
  const [selectedTransaction, setSelectedTransaction] = useState<TransactionDetail | null>(null);
  const [riskScoring, setRiskScoring] = useState<RiskScoringOverview | null>(null);
  const [txnFilters, setTxnFilters] = useState<TransactionFiltersState>({
    search: "",
    start_date: "",
    end_date: "",
    min_amount: "",
    max_amount: "",
    txn_type: "ALL",
    risk_level: "ALL",
    status: "ALL",
    pattern: "ALL",
    sort_by: "occurred_at",
    sort_dir: "desc",
  });

  // Alert management directory & 360 detail (30 default)
  const [alertPageSize, setAlertPageSize] = useState(30);
  const [alerts, setAlerts] = useState<AlertListItem[]>([]);
  const [totalAlerts, setTotalAlerts] = useState(0);
  const [alertPage, setAlertPage] = useState(0);
  const [selectedAlert, setSelectedAlert] = useState<AlertDetail | null>(null);
  const [alertFilters, setAlertFilters] = useState<AlertFiltersState>({
    search: "",
    severity: "ALL",
    rule_id: "ALL",
    status: "ALL",
    owner_analyst: "ALL",
    sla_breached: "ALL",
    start_date: "",
    end_date: "",
    sort_by: "risk_score",
    sort_dir: "desc",
  });

  // Dynamic Blank Space Tracker: Only displays the architectural watermark when right content is taller than the sidebar
  const [extraGap, setExtraGap] = useState<number>(0);
  const sidebarContainerRef = useRef<HTMLDivElement>(null);
  const workspaceContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateGap = () => {
      if (!sidebarContainerRef.current || !workspaceContainerRef.current) return;
      const sH = sidebarContainerRef.current.offsetHeight;
      const wH = workspaceContainerRef.current.offsetHeight;
      setExtraGap(wH - sH);
    };

    updateGap();

    const ro = new ResizeObserver(() => {
      updateGap();
    });

    if (sidebarContainerRef.current) ro.observe(sidebarContainerRef.current);
    if (workspaceContainerRef.current) ro.observe(workspaceContainerRef.current);
    window.addEventListener("resize", updateGap);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateGap);
    };
  }, [tab]);

  useEffect(() => {
    document.title = "YottaFlex | RiskOS";
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const inInput =
        target != null &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setShowSpotlight((s) => !s);
      } else if (e.key === "?" && !inInput) {
        e.preventDefault();
        setShowShortcuts((s) => !s);
      } else if (e.key === "Escape") {
        setShowSpotlight(false);
        setShowNotifs(false);
        setShowShortcuts(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add("dark");
      localStorage.setItem("yottaflex_theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("yottaflex_theme", "light");
    }
  }, [darkMode]);

  // Track pointer position & directional refraction angle across glass containers (excluding navbar docks)
  useEffect(() => {
    const selector =
      ".liquid-glass, .liquid-glass-hero, .liquid-glass-rose, .liquid-glass-amber, .liquid-glass-emerald, .overview-glass-sidebar, .ybot-glass-box, .ybot-glass-icon";
    const onMove = (e: MouseEvent) => {
      if (!(e.target instanceof Element)) return;
      let box = e.target.closest<HTMLElement>(selector);
      while (box) {
        const rect = box.getBoundingClientRect();
        const lx = e.clientX - rect.left;
        const ly = e.clientY - rect.top;
        const dx = e.clientX - (rect.left + rect.width / 2);
        const dy = e.clientY - (rect.top + rect.height / 2);
        const ang = Math.atan2(dx, -dy) * (180 / Math.PI);
        box.style.setProperty("--mx", `${lx}px`);
        box.style.setProperty("--my", `${ly}px`);
        box.style.setProperty("--bx", `${lx}px`);
        box.style.setProperty("--by", `${ly}px`);
        box.style.setProperty("--ang", `${ang.toFixed(1)}deg`);
        box = box.parentElement ? box.parentElement.closest<HTMLElement>(selector) : null;
      }
    };
    document.addEventListener("mousemove", onMove, { passive: true });
    return () => document.removeEventListener("mousemove", onMove);
  }, []);

  // Verify existing session token on boot
  useEffect(() => {
    const tok = getStoredToken();
    if (!tok) {
      setAuthChecked(true);
      return;
    }
    api.auth
      .me()
      .then((res) => setUser(res.user))
      .catch(() => setStoredToken(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const applyPreferences = useCallback((prefs: UserPreferences, applyLandingTab = false) => {
    if (prefs.default_page_size >= 5 && prefs.default_page_size <= 200) {
      setQueuePageSize(prefs.default_page_size);
      setCustPageSize(prefs.default_page_size);
      setAcctPageSize(prefs.default_page_size);
      setTxnPageSize(prefs.default_page_size);
      setAlertPageSize(prefs.default_page_size);
    }
    if (applyLandingTab && prefs.default_tab) {
      const validTabs: Tab[] = ["overview", "queue", "customers", "accounts", "transactions", "alerts", "quarantine", "evaluation", "governance"];
      if (validTabs.includes(prefs.default_tab as Tab)) {
        setTab(prefs.default_tab as Tab);
      }
    }
  }, []);

  const refreshNotifications = useCallback(async () => {
    if (!user) return;
    try {
      const res = await api.notifications();
      setNotifications(res.items);
      setUnreadCount(res.unread_count);
    } catch {
      // non-fatal header poll
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    api.preferences().then((prefs) => applyPreferences(prefs, true)).catch(() => {});
    refreshNotifications();
  }, [user, applyPreferences, refreshNotifications]);

  const refreshQueue = useCallback(async () => {
    if (!user) return;
    const res = await api.cases({
      sort,
      tier,
      status,
      linkage,
      search,
      assigned_analyst: queueAssignee,
      sla_breached: queueSla === "ALL" ? undefined : queueSla,
      min_exposure: queueMinExp,
      max_exposure: queueMaxExp,
      start_date: queueStartDate,
      end_date: queueEndDate,
      limit: queuePageSize,
      offset: queuePage * queuePageSize,
    });
    setCases(res.items);
    setTotalCases(res.total);
  }, [user, sort, tier, status, linkage, search, queueAssignee, queueSla, queueMinExp, queueMaxExp, queueStartDate, queueEndDate, queuePage, queuePageSize]);

  const refreshCustomers = useCallback(async () => {
    if (!user) return;
    const res = await api.customers({
      search: custSearch,
      kyc_tier: custKyc,
      risk_rating: custRisk,
      account_status: custAcctStatus,
      multi_suspicious: custMultiSuspicious ? "1" : "0",
      limit: custPageSize,
      offset: custPage * custPageSize,
    });
    setCustomers(res.items);
    setTotalCustomers(res.total);
  }, [user, custSearch, custKyc, custRisk, custAcctStatus, custMultiSuspicious, custPage, custPageSize]);

  const refreshAccounts = useCallback(async () => {
    if (!user) return;
    const res = await api.accounts({
      search: acctSearch,
      status: acctStatus,
      dormant_reactivated: acctDormant ? "1" : "0",
      limit: acctPageSize,
      offset: acctPage * acctPageSize,
    });
    setAccounts(res.items);
    setTotalAccounts(res.total);
  }, [user, acctSearch, acctStatus, acctDormant, acctPage, acctPageSize]);

  const refreshTransactions = useCallback(async () => {
    if (!user) return;
    const res = await api.transactions({
      search: txnFilters.search,
      start_date: txnFilters.start_date,
      end_date: txnFilters.end_date,
      min_amount: txnFilters.min_amount,
      max_amount: txnFilters.max_amount,
      txn_type: txnFilters.txn_type,
      risk_level: txnFilters.risk_level,
      status: txnFilters.status,
      pattern: txnFilters.pattern,
      sort_by: txnFilters.sort_by,
      sort_dir: txnFilters.sort_dir,
      limit: txnPageSize,
      offset: txnPage * txnPageSize,
    });
    setTransactions(res.items);
    setTotalTransactions(res.total);
  }, [user, txnFilters, txnPage, txnPageSize]);

  const refreshAlerts = useCallback(async () => {
    if (!user) return;
    const res = await api.alerts({
      search: alertFilters.search,
      severity: alertFilters.severity,
      rule_id: alertFilters.rule_id,
      status: alertFilters.status,
      owner_analyst: alertFilters.owner_analyst,
      sla_breached: alertFilters.sla_breached === "ALL" ? undefined : alertFilters.sla_breached,
      start_date: alertFilters.start_date,
      end_date: alertFilters.end_date,
      sort_by: alertFilters.sort_by,
      sort_dir: alertFilters.sort_dir,
      limit: alertPageSize,
      offset: alertPage * alertPageSize,
    });
    setAlerts(res.items);
    setTotalAlerts(res.total);
  }, [user, alertFilters, alertPage, alertPageSize]);

  const refreshDashboard = useCallback(async () => {
    if (!user) return;
    const res = await api.dashboard(dashFilters);
    setDashboard(res);
  }, [user, dashFilters]);

  const refreshAll = useCallback(async () => {
    if (!user) return;
    try {
      const [ov, q, ev, ru, rs] = await Promise.all([
        api.overview(),
        api.quarantine(),
        api.evaluation(),
        api.rules(),
        api.riskScoring(),
      ]);
      setOverview(ov);
      setQuarantine(q);
      setEvaluation(ev);
      setRules(ru.rules);
      setRiskScoring(rs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workbench data");
    }
  }, [user]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    refreshDashboard().catch((err) => setError(err instanceof Error ? err.message : "Dashboard error"));
  }, [refreshDashboard]);

  useEffect(() => {
    const timer = setTimeout(() => {
      refreshQueue().catch((err) => setError(err instanceof Error ? err.message : "Queue fetch error"));
    }, 120);
    return () => clearTimeout(timer);
  }, [refreshQueue]);

  useEffect(() => {
    const timer = setTimeout(() => {
      refreshCustomers().catch((err) => setError(err instanceof Error ? err.message : "Customer fetch error"));
    }, 150);
    return () => clearTimeout(timer);
  }, [refreshCustomers]);

  useEffect(() => {
    const timer = setTimeout(() => {
      refreshAccounts().catch((err) => setError(err instanceof Error ? err.message : "Account fetch error"));
    }, 150);
    return () => clearTimeout(timer);
  }, [refreshAccounts]);

  useEffect(() => {
    const timer = setTimeout(() => {
      refreshTransactions().catch((err) => setError(err instanceof Error ? err.message : "Transaction fetch error"));
    }, 150);
    return () => clearTimeout(timer);
  }, [refreshTransactions]);

  useEffect(() => {
    const timer = setTimeout(() => {
      refreshAlerts().catch((err) => setError(err instanceof Error ? err.message : "Alert fetch error"));
    }, 150);
    return () => clearTimeout(timer);
  }, [refreshAlerts]);

  const handleSelectAlert = async (alertId: string) => {
    try {
      setError(null);
      setTab("alerts");
      const det = await api.alertDetail(alertId);
      setSelectedAlert(det);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert detail");
    }
  };

  const handleSelectCase = async (caseId: string) => {
    try {
      setError(null);
      setTab("dossier");
      const d = await api.dossier(caseId);
      setDossier(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case dossier");
    }
  };

  const handleSelectCustomer = async (customerId: string) => {
    try {
      setError(null);
      setTab("customers");
      const prof = await api.customerProfile(customerId);
      setSelectedCustomer(prof);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer profile");
    }
  };

  const handleSelectAccount = async (accountId: string) => {
    try {
      setError(null);
      setTab("accounts");
      const detail = await api.accountDetail(accountId);
      setSelectedAccount(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load account detail");
    }
  };

  const handleSelectTransaction = async (transactionId: string) => {
    try {
      setError(null);
      setTab("transactions");
      const det = await api.transactionDetail(transactionId);
      setSelectedTransaction(det);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transaction detail");
    }
  };

  const handleSubmitAction = async (payload: {
    analyst_id: string;
    action_type: string;
    rationale: string;
  }): Promise<string> => {
    if (!dossier) return "";
    const cid = dossier.case.case_id;
    const res = await api.submitAction(cid, payload);
    const [updated] = await Promise.all([api.dossier(cid), refreshQueue(), refreshAll(), refreshDashboard()]);
    setDossier(updated);
    return `Recorded ${res.action.action_id} → ${res.new_status}`;
  };

  const handleLogout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore
    }
    setStoredToken(null);
    setUser(null);
    setShowProfile(false);
  };

  const handleBotAction = (act: BotAction) => {
    if (act.type === "tab") {
      setTab(act.id as Tab);
    } else if (act.type === "case") {
      handleSelectCase(act.id);
    } else if (act.type === "alert") {
      handleSelectAlert(act.id);
    } else if (act.type === "txn") {
      handleSelectTransaction(act.id);
    } else if (act.type === "account") {
      handleSelectAccount(act.id);
    } else if (act.type === "customer") {
      handleSelectCustomer(act.id);
    }
  };

  const [chameleonWave, setChameleonWave] = useState<{
    active: boolean;
    toDark: boolean;
    x: number;
    y: number;
  }>({ active: false, toDark: false, x: 0, y: 0 });
  const waveOverlayRef = useRef<HTMLDivElement>(null);
  const waveCrestRef = useRef<HTMLDivElement>(null);
  const waveAnimFrameRef = useRef<number | null>(null);

  const triggerChameleonThemeFlow = useCallback(
    (targetDark: boolean, event?: React.MouseEvent<HTMLElement> | React.KeyboardEvent<HTMLElement>) => {
      const root = document.documentElement;

      // Calculate origin coordinates of the appearance toggle button (or click)
      let x = window.innerWidth - 60;
      let y = 30;
      if (event && "clientX" in event && typeof event.clientX === "number" && event.clientX > 0) {
        x = event.clientX;
        y = event.clientY;
      } else if (event && event.currentTarget instanceof HTMLElement) {
        const rect = event.currentTarget.getBoundingClientRect();
        x = rect.left + rect.width / 2;
        y = rect.top + rect.height / 2;
      }

      // Max radius to reach furthest corner (bottom-left at 0, innerHeight) + feather buffer
      const maxR = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y)) + 380;

      // Cancel any ongoing animation frame
      if (waveAnimFrameRef.current) {
        cancelAnimationFrame(waveAnimFrameRef.current);
      }

      // 1. Activate chameleon mode on root DOM
      root.classList.add("chameleon-transitioning");
      if (targetDark) {
        root.classList.add("chameleon-to-dark");
        root.classList.remove("chameleon-to-light");
      } else {
        root.classList.add("chameleon-to-light");
        root.classList.remove("chameleon-to-dark");
      }

      // 2. Set theme in state and storage
      if (targetDark) {
        root.classList.add("dark");
        localStorage.setItem("yottaflex_theme", "dark");
      } else {
        root.classList.remove("dark");
        localStorage.setItem("yottaflex_theme", "light");
      }
      setDarkMode(targetDark);

      // 3. Mount chameleon wave layers synchronously
      flushSync(() => {
        setChameleonWave({ active: true, toDark: targetDark, x, y });
      });

      const startTime = performance.now();
      const duration = 960; // 960ms continuous organic chameleon flow

      const tick = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(1, elapsed / duration);
        // Ultra-smooth organic quintic ease-out curve
        const eased = 1 - Math.pow(1 - progress, 2.8);
        const currentR = eased * maxR;
        const opacity = progress > 0.75 ? Math.max(0, 1 - (progress - 0.75) / 0.25) : 1;

        if (waveOverlayRef.current) {
          waveOverlayRef.current.style.setProperty("--origin-x", `${x}px`);
          waveOverlayRef.current.style.setProperty("--origin-y", `${y}px`);
          waveOverlayRef.current.style.setProperty("--wave-r", `${currentR.toFixed(1)}px`);
        }
        if (waveCrestRef.current) {
          waveCrestRef.current.style.setProperty("--origin-x", `${x}px`);
          waveCrestRef.current.style.setProperty("--origin-y", `${y}px`);
          waveCrestRef.current.style.setProperty("--wave-r", `${currentR.toFixed(1)}px`);
          waveCrestRef.current.style.opacity = opacity.toFixed(3);
        }

        if (progress < 1) {
          waveAnimFrameRef.current = requestAnimationFrame(tick);
        } else {
          setChameleonWave({ active: false, toDark: targetDark, x, y });
          root.classList.remove("chameleon-transitioning", "chameleon-to-dark", "chameleon-to-light");
        }
      };

      waveAnimFrameRef.current = requestAnimationFrame(tick);
    },
    []
  );

  if (!authChecked) {
    return (
      <div className="yf-backdrop-light min-h-screen flex items-center justify-center text-xs font-semibold text-slate-700 dark:text-zinc-300">
        Verifying session...
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <AuthScreen
          darkMode={darkMode}
          onToggleTheme={() => triggerChameleonThemeFlow(!darkMode)}
          onAuthenticated={(u) => setUser(u)}
        />
        <YottaBotWidget isAuthenticated={false} />
        {chameleonWave.active && (
          <div
            ref={waveCrestRef}
            aria-hidden="true"
            className={`chameleon-crest-wave ${
              chameleonWave.toDark ? "chameleon-crest-to-dark" : "chameleon-crest-to-light"
            }`}
          />
        )}
      </>
    );
  }

  const sidebarNavItems: Array<NavItem<Tab>> = [
    { id: "overview", label: "Overview", icon: <LayoutDashboard className="w-4 h-4" /> },
    {
      id: "queue",
      label: "Queue",
      icon: <Layers className="w-4 h-4" />,
      badge: overview?.counts?.open_cases,
    },
    { id: "customers", label: "Customers", icon: <Users className="w-4 h-4" /> },
    { id: "accounts", label: "Accounts", icon: <CreditCard className="w-4 h-4" /> },
    { id: "transactions", label: "Txns", icon: <ArrowLeftRight className="w-4 h-4" /> },
    { id: "network", label: "Flow Graph", icon: <GitFork className="w-4 h-4" /> },
    { id: "alerts", label: "Alerts", icon: <Bell className="w-4 h-4" /> },
    {
      id: "dossier",
      label: dossier ? dossier.case.case_id.replace("CASE-2026-", "Case #") : "Dossier",
      icon: <FolderSearch className="w-4 h-4" />,
    },
    {
      id: "quarantine",
      label: "Quarantine",
      icon: <ShieldAlert className="w-4 h-4" />,
      badge: quarantine?.total_exceptions,
    },
    { id: "evaluation", label: "Evaluation", icon: <BarChart3 className="w-4 h-4" /> },
    { id: "governance", label: "Governance", icon: <Scale className="w-4 h-4" /> },
  ];

  const handleMarkAllRead = async () => {
    try {
      await api.markNotificationsRead();
      await refreshNotifications();
    } catch {
      // non-fatal
    }
  };

  const handleOpenNotif = async (item: NotificationItem) => {
    if (!item.is_read) {
      api.markNotificationsRead(item.notif_id).then(refreshNotifications).catch(() => {});
    }
    setShowNotifs(false);
    if (item.entity_type === "case" && item.entity_id) handleSelectCase(item.entity_id);
    else if (item.entity_type === "alert" && item.entity_id) handleSelectAlert(item.entity_id);
    else if (item.entity_type === "customer" && item.entity_id) handleSelectCustomer(item.entity_id);
    else if (item.entity_type === "account" && item.entity_id) handleSelectAccount(item.entity_id);
    else if (item.entity_type === "governance") setTab("governance");
  };

  const renderNotifBell = (variant: "overview" | "dock") => (
    <NotificationBellButton
      open={showNotifs}
      unreadCount={unreadCount}
      variant={variant}
      onOpenFromRect={(rect) => {
        setNotifAnchor(rect);
        setShowNotifs(true);
        refreshNotifications();
      }}
    />
  );

  const renderShortcutsBtn = (extraClass = "") => (
    <button
      type="button"
      onClick={() => setShowShortcuts(true)}
      title="Keyboard Shortcuts (?)"
      aria-label="Keyboard Shortcuts"
      className={`glass-pill chameleon-btn-shortcuts h-8 inline-flex items-center gap-1.5 px-2.5 rounded-full text-xs font-semibold text-slate-800 dark:text-white shrink-0 ${extraClass}`}
    >
      <Keyboard className="w-3.5 h-3.5 text-slate-700 dark:text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />
      <span className="hidden xl:inline font-mono text-[10px] text-slate-700 dark:text-zinc-200">?</span>
    </button>
  );

  const getGreetingKicker = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return { text: "GOOD MORNING", icon: <Sun className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 shrink-0" /> };
    }
    if (hour >= 12 && hour < 15) {
      return { text: "GOOD AFTERNOON", icon: <Sun className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 shrink-0" /> };
    }
    // After 3:00 PM (15:00 to 04:59) -> always GOOD EVENING (never good night)
    return {
      text: "GOOD EVENING",
      icon: hour >= 15 && hour < 19
        ? <Sun className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 shrink-0" />
        : <Moon className="w-3.5 h-3.5 text-slate-400 dark:text-white/80 shrink-0" />,
    };
  };

  const renderProfileBtn = (extraClass = "") => (
    <button
      type="button"
      onClick={() => setShowProfile(true)}
      title={`Profile: ${user.full_name || "Analyst"}`}
      aria-label="User Profile"
      className={`glass-pill chameleon-btn-profile w-8 h-8 rounded-full flex items-center justify-center text-slate-700 dark:text-white/90 shrink-0 ${extraClass}`}
    >
      <UserCircle2 className="w-4 h-4 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />
    </button>
  );

  const renderThemeSlider = (extraClass = "") => (
    <div
      role="button"
      tabIndex={0}
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const clickedRight = clickX >= rect.width / 2;
        // Clicking right side activates Dark Mode (slides right)
        // Clicking left side activates Light Mode (slides left)
        // If clicking the current active side, toggle to the opposite side
        const nextDark = clickedRight && !darkMode ? true : !clickedRight && darkMode ? false : !darkMode;
        triggerChameleonThemeFlow(nextDark, e);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          triggerChameleonThemeFlow(!darkMode, e);
        }
      }}
      title={darkMode ? "Theme: Dark Mode (Click to switch to Light)" : "Theme: Light Mode (Click to switch to Dark)"}
      aria-label="Toggle Light / Dark Theme"
      className={`glass-theme-slider-track chameleon-btn-theme shrink-0 cursor-pointer ${extraClass}`}
    >
      {/* Elevated 3D Transparent Liquid Glass Sliding Thumb */}
      <div
        className="glass-theme-slider-thumb pointer-events-none"
        style={{
          transform: darkMode ? "translate3d(32px, 0, 0)" : "translate3d(0, 0, 0)",
        }}
      />

      {/* Sun Option (Left) */}
      <div
        className={`w-[30px] h-7 rounded-full flex items-center justify-center relative z-10 pointer-events-none transition-all duration-300 ${
          !darkMode
            ? "text-amber-500 scale-105 drop-shadow-[0_1px_2px_rgba(0,0,0,0.2)] drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]"
            : "text-slate-400 dark:text-white/40 opacity-40 scale-95"
        }`}
      >
        <Sun className="w-3.5 h-3.5" />
      </div>

      {/* Moon Option (Right) */}
      <div
        className={`w-[30px] h-7 rounded-full flex items-center justify-center relative z-10 pointer-events-none transition-all duration-300 ${
          darkMode
            ? "text-cyan-300 scale-105 drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)] drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]"
            : "text-slate-400 dark:text-white/40 opacity-40 scale-95"
        }`}
      >
        <Moon className="w-3.5 h-3.5" />
      </div>
    </div>
  );

  const currentTabMeta = {
    overview: {
      title: "Executive Overview",
      subtitle: "Deterministic Risk Indicators, Ledger KPIs & Real-Time Intelligence",
      icon: <LayoutDashboard className="w-4 h-4" />,
      badge: overview?.scale ? `${overview.scale.toUpperCase()} SCALE` : undefined,
    },
    queue: {
      title: "Priority Case Queue",
      subtitle: "Entity-Linked Multi-Alert Case Triage & Prioritization",
      icon: <Layers className="w-4 h-4" />,
      badge: totalCases ? `${totalCases.toLocaleString()} Cases` : undefined,
    },
    customers: {
      title: "Customers Directory",
      subtitle: "KYC Profiles, Risk Ratings & Counterparty Corridors",
      icon: <Users className="w-4 h-4" />,
      badge: totalCustomers ? `${totalCustomers.toLocaleString()} Customers` : undefined,
    },
    accounts: {
      title: "Accounts Ledger",
      subtitle: "Double-Entry Balance Reconciliation & Burst Profiling",
      icon: <CreditCard className="w-4 h-4" />,
      badge: totalAccounts ? `${totalAccounts.toLocaleString()} Accounts` : undefined,
    },
    transactions: {
      title: "Transactions Ledger",
      subtitle: "Reconciled Debit/Credit Movements & Behavioral Forensics",
      icon: <ArrowLeftRight className="w-4 h-4" />,
      badge: totalTransactions ? `${totalTransactions.toLocaleString()} Txns` : undefined,
    },
    network: {
      title: "Transaction & Money Flow Graph",
      subtitle: "Investigate financial relationships, trace fund movements and identify suspicious transaction networks",
      icon: <GitFork className="w-4 h-4" />,
      badge: "Graph Intelligence Active",
    },
    alerts: {
      title: "Rule-Triggered Alerts",
      subtitle: "Transparent Rule Factual Attributions & Fatigue Analysis",
      icon: <Bell className="w-4 h-4" />,
      badge: totalAlerts ? `${totalAlerts.toLocaleString()} Alerts` : undefined,
    },
    dossier: {
      title: dossier ? `Investigation Dossier · ${dossier.case.case_id}` : "Case Dossier",
      subtitle: "Entity Network Graph, Chronology, GoAML XML & Cryptographic Seal",
      icon: <FolderSearch className="w-4 h-4" />,
      badge: dossier ? `Score ${Math.round(dossier.case.priority_score)}` : undefined,
    },
    quarantine: {
      title: "Exception Quarantine Queue",
      subtitle: "9-Check Integrity Violations Isolated from Clean Processing",
      icon: <ShieldAlert className="w-4 h-4" />,
      badge: quarantine ? `${quarantine.total_exceptions} Quarantined` : undefined,
    },
    evaluation: {
      title: "Model Calibration & Evaluation",
      subtitle: "Zero Ground-Truth Leakage Lift Curves, Score Histograms & PSI Drift",
      icon: <BarChart3 className="w-4 h-4" />,
      badge: "Zero-Leakage Verified",
    },
    governance: {
      title: "Governance, Controls & Audits",
      subtitle: "Sanctions/PEP Screening, Four-Eyes Controls & Tamper-Evident Chain",
      icon: <Scale className="w-4 h-4" />,
      badge: "RBAC Active",
    },
  }[tab];

  return (
    <div className="relative min-h-screen flex flex-col text-slate-900 dark:text-zinc-100 overflow-x-hidden">
      {/* Dynamic Chameleon Dual Atmospheric Background (Zero-jerk gradual color flow) */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        {/* Base Static Atmospheric Backdrop */}
        <div
          className={`absolute inset-0 ${
            darkMode && !chameleonWave.active
              ? "yf-backdrop-dark"
              : !darkMode && !chameleonWave.active
              ? "yf-backdrop-light"
              : chameleonWave.toDark
              ? "yf-backdrop-light"
              : "yf-backdrop-dark"
          }`}
        >
          {/* Base Atmospheric Orbs & Watermark (Displaying previous theme during active wave, switching instantly with 0 change on completion) */}
          <div
            className={`bg-orb-top-right absolute -top-24 -right-24 w-[560px] h-[560px] rounded-[72px] rotate-12 backdrop-blur-3xl ${
              darkMode && !chameleonWave.active
                ? "bg-azure-500/[0.04] border border-azure-400/[0.12]"
                : !darkMode && !chameleonWave.active
                ? "bg-white/25 border border-white/45"
                : chameleonWave.toDark
                ? "bg-white/25 border border-white/45"
                : "bg-azure-500/[0.04] border border-azure-400/[0.12]"
            }`}
          />
          <div
            className={`bg-orb-bottom-left absolute bottom-[-120px] -left-24 w-[460px] h-[460px] rounded-[64px] -rotate-12 ${
              darkMode && !chameleonWave.active
                ? "bg-white/[0.02] border border-white/[0.05]"
                : !darkMode && !chameleonWave.active
                ? "bg-white/20 border border-white/40"
                : chameleonWave.toDark
                ? "bg-white/20 border border-white/40"
                : "bg-white/[0.02] border border-white/[0.05]"
            }`}
          />
          <img
            src="/yottaflex-logo.webp"
            alt=""
            className={`bg-watermark-logo absolute right-[4%] bottom-[8%] w-[640px] max-w-[62vw] select-none ${
              darkMode && !chameleonWave.active
                ? "opacity-[0.24] brightness-125 contrast-100 saturate-150 drop-shadow-[0_12px_36px_rgba(22,90,220,0.35)]"
                : !darkMode && !chameleonWave.active
                ? "opacity-[0.27] brightness-[0.82] contrast-[1.14] saturate-[1.18] drop-shadow-[0_14px_40px_rgba(10,40,110,0.38)]"
                : chameleonWave.toDark
                ? "opacity-[0.27] brightness-[0.82] contrast-[1.14] saturate-[1.18] drop-shadow-[0_14px_40px_rgba(10,40,110,0.38)]"
                : "opacity-[0.24] brightness-125 contrast-100 saturate-150 drop-shadow-[0_12px_36px_rgba(22,90,220,0.35)]"
            }`}
          />
          <div
            className={`bg-watermark-text hidden lg:block absolute right-10 bottom-6 text-[88px] font-bold tracking-tighter select-none leading-none ${
              darkMode && !chameleonWave.active
                ? "text-azure-400/[0.12]"
                : !darkMode && !chameleonWave.active
                ? "text-slate-900/[0.10]"
                : chameleonWave.toDark
                ? "text-slate-900/[0.10]"
                : "text-azure-400/[0.12]"
            }`}
          >
            YottaFlex
          </div>
        </div>

        {/* Chameleon Flowing Wave Backdrop Layer (Soft 280px feathered radial gradient) */}
        {chameleonWave.active && (
          <div
            ref={waveOverlayRef}
            className={`chameleon-bg-wave absolute inset-0 ${
              chameleonWave.toDark ? "yf-backdrop-dark" : "yf-backdrop-light"
            }`}
          >
            {/* Target theme's orbs & watermark revealed dynamically from top-right to bottom-left as wavefront expands */}
            <div
              className={`absolute -top-24 -right-24 w-[560px] h-[560px] rounded-[72px] rotate-12 backdrop-blur-3xl ${
                chameleonWave.toDark
                  ? "bg-azure-500/[0.04] border border-azure-400/[0.12]"
                  : "bg-white/25 border border-white/45"
              }`}
            />
            <div
              className={`absolute bottom-[-120px] -left-24 w-[460px] h-[460px] rounded-[64px] -rotate-12 ${
                chameleonWave.toDark
                  ? "bg-white/[0.02] border border-white/[0.05]"
                  : "bg-white/20 border border-white/40"
              }`}
            />
            <img
              src="/yottaflex-logo.webp"
              alt=""
              className={`absolute right-[4%] bottom-[8%] w-[640px] max-w-[62vw] select-none ${
                chameleonWave.toDark
                  ? "opacity-[0.24] brightness-125 contrast-100 saturate-150 drop-shadow-[0_12px_36px_rgba(22,90,220,0.35)]"
                  : "opacity-[0.27] brightness-[0.82] contrast-[1.14] saturate-[1.18] drop-shadow-[0_14px_40px_rgba(10,40,110,0.38)]"
              }`}
            />
            <div
              className={`hidden lg:block absolute right-10 bottom-6 text-[88px] font-bold tracking-tighter select-none leading-none ${
                chameleonWave.toDark ? "text-azure-400/[0.12]" : "text-slate-900/[0.10]"
              }`}
            >
              YottaFlex
            </div>
          </div>
        )}
      </div>

      {/* Unified Persistent Layout: Left Sidebar + Right Fluid Expanding Workspace */}
      <div className="relative z-10 flex-1 max-w-[1720px] w-full mx-auto px-4 sm:px-5 py-4 flex flex-col lg:flex-row items-start gap-4 lg:gap-5">
        {/* Left Column: Sidebar + Dynamic Adaptive Blank-Space Watermark */}
        <div className="w-full lg:w-auto shrink-0 flex flex-col items-center">
          <div ref={sidebarContainerRef} className="w-full">
            <OverviewSidebar
              items={sidebarNavItems}
              activeId={tab}
              onChange={setTab}
              user={user}
              onOpenProfile={() => setShowProfile(true)}
              onOpenSupport={() => window.dispatchEvent(new CustomEvent("yottabot:open"))}
              isCollapsed={tab !== "overview"}
            />
          </div>

          {/* Translucent Subtle Monoline Sans Vertical Architectural Watermark (Image 06: Minimal · Elegant · Contemporary) */}
          {extraGap >= 280 && (
            <div
              aria-hidden="true"
              className="hidden lg:flex flex-col items-center justify-center gap-3 py-6 select-none pointer-events-none overflow-hidden transition-opacity duration-300"
              style={{
                height: Math.min(extraGap - 40, 780),
                maxHeight: extraGap - 40,
              }}
            >
              <span
                className="font-light text-[80px] sm:text-[98px] lg:text-[120px] tracking-[0.04em] text-slate-900/[0.13] dark:text-sky-100/[0.11] select-none leading-none drop-shadow-sm"
                style={{
                  writingMode: "vertical-rl",
                  transform: "rotate(180deg)",
                  fontFamily: '"Urbanist", "Outfit", -apple-system, BlinkMacSystemFont, "SF Pro Display", "Plus Jakarta Sans", sans-serif',
                  fontWeight: 300,
                }}
              >
                RiskOS<sup className="text-[0.34em] font-light tracking-normal align-super ml-1 opacity-80">TM</sup>
              </span>
              <div
                className="flex items-center gap-1.5 text-xs font-bold tracking-tight text-slate-900/[0.22] dark:text-azure-400/[0.28] select-none"
                style={{
                  fontFamily: '"Plus Jakarta Sans", sans-serif',
                }}
              >
                <span className="text-[10px] tracking-widest uppercase font-semibold text-slate-800/40 dark:text-zinc-400/50">By</span>
                <span className="text-[12.5px] font-bold tracking-tight">YottaFlex.ai</span>
              </div>
            </div>
          )}
        </div>

        {/* Right Workspace: Smoothly expands to the left when the sidebar shrinks */}
        <div
          ref={workspaceContainerRef}
          className="flex-1 min-w-0 w-full flex flex-col gap-5 transition-[width,margin] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]"
        >
          {/* Top Unified Executive Utility Header (Active Section Breadcrumb + Utilities, NO long nav bar) */}
          <header className="sticky top-3 z-30 w-full">
            {tab === "overview" ? (
              <div className="px-2 sm:px-3 py-1 flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Left: iOS Glass Font Welcome Note matching Image */}
                <div className="min-w-0">
                  {/* Kicker: GOOD AFTERNOON ☼ */}
                  <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-[0.16em] uppercase text-slate-500 dark:text-zinc-400 mb-1">
                    <span>{getGreetingKicker().text}</span>
                    {getGreetingKicker().icon}
                  </div>

                  {/* Heading: Vertical blue line + Welcome back, Aman Reddy */}
                  <div className="flex items-center gap-2.5">
                    <span className="w-1 h-6 sm:h-7 rounded-full bg-gradient-to-b from-sky-400 to-azure-600 shadow-[0_0_10px_rgba(56,189,248,0.7)] shrink-0" />
                    <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-950 dark:text-white leading-tight">
                      <span>Welcome back, </span>
                      <span className="text-azure-600 dark:text-sky-400 font-bold">
                        {user.full_name || "Analyst"}
                      </span>
                    </h1>
                  </div>

                  {/* Subtitle matching image */}
                  <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 font-normal mt-1 pl-3.5">
                    Here's what's happening across your risk operations today.
                  </p>
                </div>

                {/* Right Controls: Independent floating glass pills (NO enclosing long panel) */}
                <div className="flex items-center gap-2 pr-0.5 shrink-0 self-end md:self-auto">
                  <button
                    type="button"
                    onClick={() => setShowSpotlight(true)}
                    title="Global Spotlight Search (Cmd/Ctrl + K)"
                    className="glass-pill chameleon-btn-search h-8 inline-flex items-center gap-1.5 px-3 rounded-full text-xs font-semibold text-slate-800 dark:text-white shrink-0"
                  >
                    <Search className="w-3.5 h-3.5 text-slate-700 dark:text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />
                    <span className="hidden md:inline font-mono ios-num text-[10px] text-slate-700 dark:text-zinc-200">⌘K</span>
                  </button>

                  {renderNotifBell("dock")}

                  {renderShortcutsBtn()}

                  {renderProfileBtn()}

                  {renderThemeSlider()}
                </div>
              </div>
            ) : (
              <div className="liquid-glass rounded-full px-4 sm:px-5 py-2.5 flex items-center justify-between gap-3 shadow-[0_8px_32px_rgba(0,0,0,0.12)]">
                {/* Left: Active Section Indicator / Breadcrumb */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="w-8 h-8 rounded-full glass-pill flex items-center justify-center shrink-0 text-slate-700 dark:text-white/90">
                    {currentTabMeta.icon}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold tracking-tight text-slate-950 dark:text-white truncate">
                        {currentTabMeta.title}
                      </span>
                      {currentTabMeta.badge && (
                        <span className="badge-glass badge-glass-blue font-mono ios-num text-[10px] leading-tight px-2 py-0.5 rounded-full">
                          {currentTabMeta.badge}
                        </span>
                      )}
                    </div>
                    <div className="hidden sm:block text-[11px] font-medium text-slate-500 dark:text-zinc-400 truncate">
                      {currentTabMeta.subtitle}
                    </div>
                  </div>
                </div>

                {/* Right Controls: Spotlight Search + Notifications + Shortcuts + Neat User Profile Icon + Realistic Glass Theme Slider */}
                <div className="flex items-center gap-2 pr-0.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => setShowSpotlight(true)}
                    title="Global Spotlight Search (Cmd/Ctrl + K)"
                    className="glass-pill chameleon-btn-search h-8 inline-flex items-center gap-1.5 px-3 rounded-full text-xs font-semibold text-slate-800 dark:text-white shrink-0"
                  >
                    <Search className="w-3.5 h-3.5 text-slate-700 dark:text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />
                    <span className="hidden md:inline font-mono ios-num text-[10px] text-slate-700 dark:text-zinc-200">⌘K</span>
                  </button>

                  {renderNotifBell("dock")}

                  {renderShortcutsBtn()}

                  {renderProfileBtn()}

                  {renderThemeSlider()}
                </div>
              </div>
            )}
          </header>

          <main className="w-full">
            {error && (
              <div className="mb-4 liquid-glass rounded-2xl border-rose-300/60 dark:border-rose-500/30 px-4 py-3 text-xs font-semibold text-rose-700 dark:text-rose-300 flex justify-between">
                <span>{error}</span>
                <button type="button" onClick={() => setError(null)} className="underline">
                  Dismiss
                </button>
              </div>
            )}

            {tab === "overview" && (
              <DashboardView
                data={dashboard}
                darkMode={darkMode}
                filters={dashFilters}
                onFiltersChange={setDashFilters}
                onOpenCustomer={handleSelectCustomer}
                onOpenAccount={handleSelectAccount}
                onOpenTransaction={handleSelectTransaction}
                onFilterTransactionsRisk={(lvl) => {
                  setSelectedTransaction(null);
                  setTxnFilters((prev) => ({ ...prev, risk_level: lvl, pattern: "ALL" }));
                  setTxnPage(0);
                  setTab("transactions");
                }}
                onOpenCase={handleSelectCase}
              />
            )}

        {tab === "queue" && (
          <QueueView
            overview={overview}
            evaluation={evaluation}
            cases={cases}
            totalCases={totalCases}
            page={queuePage}
            pageSize={queuePageSize}
            sort={sort}
            tier={tier}
            status={status}
            linkage={linkage}
            search={search}
            assignedAnalyst={queueAssignee}
            slaFilter={queueSla}
            minExposure={queueMinExp}
            maxExposure={queueMaxExp}
            startDate={queueStartDate}
            endDate={queueEndDate}
            onSortChange={(v) => { setSort(v); setQueuePage(0); }}
            onTierChange={(v) => { setTier(v); setQueuePage(0); }}
            onStatusChange={(v) => { setStatus(v); setQueuePage(0); }}
            onLinkageChange={(v) => { setLinkage(v); setQueuePage(0); }}
            onSearchChange={(v) => { setSearch(v); setQueuePage(0); }}
            onAssignedAnalystChange={(v) => { setQueueAssignee(v); setQueuePage(0); }}
            onSlaFilterChange={(v) => { setQueueSla(v); setQueuePage(0); }}
            onMinExposureChange={(v) => { setQueueMinExp(v); setQueuePage(0); }}
            onMaxExposureChange={(v) => { setQueueMaxExp(v); setQueuePage(0); }}
            onStartDateChange={(v) => { setQueueStartDate(v); setQueuePage(0); }}
            onEndDateChange={(v) => { setQueueEndDate(v); setQueuePage(0); }}
            onPageChange={setQueuePage}
            onPageSizeChange={(sz) => {
              setQueuePageSize(sz);
              setQueuePage(0);
            }}
            onSelectCase={handleSelectCase}
            onQueueUpdated={async () => {
              await Promise.all([refreshQueue(), refreshAll()]);
            }}
          />
        )}

        {tab === "customers" && (
          <CustomersView
            customers={customers}
            total={totalCustomers}
            page={custPage}
            pageSize={custPageSize}
            search={custSearch}
            kycTier={custKyc}
            riskRating={custRisk}
            accountStatus={custAcctStatus}
            multiSuspicious={custMultiSuspicious}
            selectedProfile={selectedCustomer}
            onSearchChange={(v) => {
              setCustSearch(v);
              setCustPage(0);
            }}
            onKycChange={(v) => {
              setCustKyc(v);
              setCustPage(0);
            }}
            onRiskChange={(v) => {
              setCustRisk(v);
              setCustPage(0);
            }}
            onAccountStatusChange={(v) => {
              setCustAcctStatus(v);
              setCustPage(0);
            }}
            onMultiSuspiciousChange={(v) => {
              setCustMultiSuspicious(v);
              setCustPage(0);
            }}
            onPageChange={setCustPage}
            onPageSizeChange={(sz) => {
              setCustPageSize(sz);
              setCustPage(0);
            }}
            onSelectCustomer={handleSelectCustomer}
            onCloseProfile={() => setSelectedCustomer(null)}
            onOpenAccount={handleSelectAccount}
            onOpenTransaction={handleSelectTransaction}
            onOpenCase={handleSelectCase}
          />
        )}

        {tab === "accounts" && (
          <AccountsView
            accounts={accounts}
            total={totalAccounts}
            page={acctPage}
            pageSize={acctPageSize}
            search={acctSearch}
            status={acctStatus}
            dormantReactivated={acctDormant}
            selectedDetail={selectedAccount}
            onSearchChange={(v) => {
              setAcctSearch(v);
              setAcctPage(0);
            }}
            onStatusChange={(v) => {
              setAcctStatus(v);
              setAcctPage(0);
            }}
            onDormantChange={(v) => {
              setAcctDormant(v);
              setAcctPage(0);
            }}
            onPageChange={setAcctPage}
            onPageSizeChange={(sz) => {
              setAcctPageSize(sz);
              setAcctPage(0);
            }}
            onSelectAccount={handleSelectAccount}
            onCloseDetail={() => setSelectedAccount(null)}
            onOpenCustomer={handleSelectCustomer}
            onOpenTransaction={handleSelectTransaction}
          />
        )}

        {tab === "transactions" && (
          <TransactionsView
            transactions={transactions}
            total={totalTransactions}
            page={txnPage}
            pageSize={txnPageSize}
            filters={txnFilters}
            selectedDetail={selectedTransaction}
            riskScoring={riskScoring}
            userRole={user.role}
            onRefreshScoring={async () => {
              await Promise.all([refreshAll(), refreshAlerts(), refreshTransactions()]);
            }}
            onFiltersChange={(next) => {
              setTxnFilters(next);
              setTxnPage(0);
            }}
            onPageChange={setTxnPage}
            onPageSizeChange={(sz) => {
              setTxnPageSize(sz);
              setTxnPage(0);
            }}
            onSelectTransaction={handleSelectTransaction}
            onCloseDetail={() => setSelectedTransaction(null)}
            onOpenAccount={handleSelectAccount}
            onOpenCustomer={handleSelectCustomer}
          />
        )}

        {tab === "network" && (
          <NetworkIntelligenceView
            darkMode={darkMode}
            onSelectCase={handleSelectCase}
            onSelectAccount={handleSelectAccount}
            onSelectCustomer={handleSelectCustomer}
            onSelectTransaction={handleSelectTransaction}
          />
        )}

        {tab === "alerts" && (
          <AlertsView
            alerts={alerts}
            total={totalAlerts}
            page={alertPage}
            pageSize={alertPageSize}
            rules={rules}
            filters={alertFilters}
            selectedDetail={selectedAlert}
            onFiltersChange={(next) => {
              setAlertFilters(next);
              setAlertPage(0);
            }}
            onPageChange={setAlertPage}
            onPageSizeChange={(sz) => {
              setAlertPageSize(sz);
              setAlertPage(0);
            }}
            onSelectAlert={handleSelectAlert}
            onCloseDetail={() => setSelectedAlert(null)}
            onOpenTransaction={handleSelectTransaction}
            onOpenAccount={handleSelectAccount}
            onOpenCustomer={handleSelectCustomer}
            onOpenCase={handleSelectCase}
            onAlertsUpdated={async () => {
              await Promise.all([refreshAlerts(), refreshQueue(), refreshAll()]);
            }}
          />
        )}

        {tab === "dossier" && (
          <DossierView
            dossier={dossier}
            darkMode={darkMode}
            onBack={() => setTab("queue")}
            onSubmitAction={handleSubmitAction}
            onDossierUpdated={async (cid) => {
              const [updated] = await Promise.all([api.dossier(cid), refreshQueue(), refreshAll()]);
              setDossier(updated);
            }}
            onOpenCase={handleSelectCase}
          />
        )}

            {tab === "quarantine" && (
              <QuarantineView
                data={quarantine}
                onRefresh={async () => {
                  await refreshAll();
                }}
                onOpenAccount={handleSelectAccount}
                onOpenTransaction={handleSelectTransaction}
              />
            )}

            {tab === "evaluation" && <EvaluationView evaluation={evaluation} rules={rules} darkMode={darkMode} />}

            {tab === "governance" && (
              <GovernanceView
                user={user}
                onOpenCase={handleSelectCase}
                onOpenCustomer={handleSelectCustomer}
                onOpenAccount={handleSelectAccount}
                onRefreshQueue={async () => {
                  await Promise.all([refreshQueue(), refreshAlerts(), refreshAll()]);
                }}
              />
            )}
          </main>
        </div>
      </div>

      <Footer />

      <GlobalSearchModal
        open={showSpotlight}
        onClose={() => setShowSpotlight(false)}
        onSelectEntity={(group, id) => {
          if (group === "cases") handleSelectCase(id);
          else if (group === "alerts") handleSelectAlert(id);
          else if (group === "customers") handleSelectCustomer(id);
          else if (group === "accounts") handleSelectAccount(id);
          else if (group === "transactions") handleSelectTransaction(id);
          else if (group === "quarantine") setTab("quarantine");
        }}
      />

      {showProfile && (
        <ProfileModal
          user={user}
          onClose={() => setShowProfile(false)}
          onProfileUpdated={(u) => setUser(u)}
          onPreferencesUpdated={(prefs) => applyPreferences(prefs, false)}
          onLogout={handleLogout}
        />
      )}

      {showShortcuts && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/35 dark:bg-black/65 backdrop-blur-md"
          onClick={() => setShowShortcuts(false)}
        >
          <div
            className="liquid-glass-search w-full max-w-md rounded-3xl p-5 space-y-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200/70 dark:border-white/10 pb-3">
              <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
                <Keyboard className="w-4 h-4 text-azure-600 dark:text-sky-300" />
                <span>Workbench Keyboard Shortcuts</span>
              </div>
              <button
                type="button"
                onClick={() => setShowShortcuts(false)}
                className="glass-pill p-1.5 rounded-full text-slate-700 dark:text-zinc-200 bg-white/60 dark:bg-white/10 hover:bg-white/90 dark:hover:bg-white/20 border border-white/80 dark:border-white/15 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2 text-xs">
              {[
                { keys: "⌘K / Ctrl+K", desc: "Toggle Global Spotlight entity search" },
                { keys: "?", desc: "Open / close this Keyboard Shortcuts overlay" },
                { keys: "Esc", desc: "Dismiss Spotlight, Notifications, or Shortcuts modal" },
                { keys: "Click Pill", desc: "Jump directly from Notification alerts into Case Dossier" },
                { keys: "Rows / Page", desc: "Customize page density (default 30) in GlassPagination or Profile" },
              ].map((row) => (
                <div
                  key={row.keys}
                  className="flex items-center justify-between gap-3 rounded-xl bg-white/40 dark:bg-white/[0.06] backdrop-blur-md px-3 py-2 border border-white/80 dark:border-white/15"
                >
                  <span className="text-slate-800 dark:text-zinc-200 font-medium">{row.desc}</span>
                  <kbd className="glass-pill font-mono ios-num text-[11px] font-bold px-2.5 py-0.5 rounded-full text-slate-900 dark:text-white bg-white/70 dark:bg-white/10 border border-white/80 dark:border-white/20 shrink-0">
                    {row.keys}
                  </kbd>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <NotificationWindowPanel
        open={showNotifs}
        anchor={notifAnchor}
        onClose={() => setShowNotifs(false)}
        notifications={notifications}
        unreadCount={unreadCount}
        onRefresh={refreshNotifications}
        onMarkAllRead={handleMarkAllRead}
        onSelectNotification={handleOpenNotif}
      />

      <YottaBotWidget isAuthenticated={true} onAction={handleBotAction} />

      {/* Luminous Chameleon Chromatic Wavefront Crest */}
      {chameleonWave.active && (
        <div
          ref={waveCrestRef}
          aria-hidden="true"
          className={`chameleon-crest-wave ${
            chameleonWave.toDark ? "chameleon-crest-to-dark" : "chameleon-crest-to-light"
          }`}
        />
      )}
    </div>
  );
};
