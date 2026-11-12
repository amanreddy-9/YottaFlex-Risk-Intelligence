import React, { useEffect, useRef, useState } from "react";
import { Minus, RotateCcw, Send, User } from "lucide-react";
import { api } from "../api/client";

export interface BotAction {
  type: "tab" | "case" | "alert" | "txn" | "account" | "customer";
  id: string;
  label: string;
}

interface ChatMessage {
  id: string;
  role: "bot" | "user";
  text: string;
  source?: string;
  actions?: BotAction[];
}

interface YottaBotWidgetProps {
  isAuthenticated: boolean;
  onAction?: (action: BotAction) => void;
}

const SUGGESTED_QUESTIONS_AUTH = [
  "How many customers & txns?",
  "Explain all 8 risk rules",
  "Show quarantine exceptions",
  "What is Priority vs FIFO recall?",
  "Show top priority cases",
];

const SUGGESTED_QUESTIONS_GUEST = [
  "How do I sign in?",
  "Explain YottaFlex architecture",
  "Explain all 8 risk rules",
  "What CLI commands run this?",
  "How is ground truth isolated?",
];

/** Track pointer position in local element coordinates so border rim shine moves dynamically on hover. */
function trackGlassBorder(e: React.MouseEvent<HTMLElement>): void {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--bx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--by", `${e.clientY - rect.top}px`);
}

/** Render lightweight inline markdown (**bold** and `code`) cleanly without HTML injection. */
function renderInlineText(line: string): React.ReactNode {
  const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-bold text-slate-950 dark:text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          onMouseMove={trackGlassBorder}
          className="inline-block font-mono text-[10.5px] px-2 py-0.5 rounded-full ybot-glass-box text-azure-800 dark:text-sky-200"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

export const YottaBotWidget: React.FC<YottaBotWidgetProps> = ({ isAuthenticated, onAction }) => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-1",
      role: "bot",
      source: "Yotta Bot • Live Project Assistant",
      text:
        "Hi! I'm **Yotta Bot**. Ask me anything about the YottaFlex architecture, sign-in credentials, risk rules, quarantine exceptions, evaluation metrics, or enter any ID like `CASE-2026-000017`, `ALT-2026-000001`, `CUS-000001`, `ACC-CUS-000001-01`, or `TXN-2026-00000001`.",
    },
  ]);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const handleOpen = () => setOpen(true);
    window.addEventListener("yottabot:open", handleOpen);
    return () => window.removeEventListener("yottabot:open", handleOpen);
  }, []);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    if (open) {
      const timer = window.setTimeout(() => inputRef.current?.focus(), 320);
      return () => window.clearTimeout(timer);
    }
  }, [messages, open]);

  const sendQuery = async (textOverride?: string) => {
    const q = (textOverride ?? input).trim();
    if (!q || sending) return;
    if (!textOverride) setInput("");

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      role: "user",
      text: q,
    };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    try {
      const res = await api.assistantChat(q);
      setMessages((prev) => [
        ...prev,
        {
          id: `b-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          role: "bot",
          text: res.reply,
          source: res.source,
          actions: res.actions,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "bot",
          source: "Local Guide Fallback",
          text:
            err instanceof Error
              ? `Could not reach backend (${err.message}). Verify the YottaFlex server is running on port 8080.`
              : "Could not reach backend.",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const resetChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "bot",
        source: "Yotta Bot • Live Project Assistant",
        text: "Chat cleared. Ask anything about YottaFlex features, rules, metrics, or paste any entity ID!",
      },
    ]);
  };

  const prompts = isAuthenticated ? SUGGESTED_QUESTIONS_AUTH : SUGGESTED_QUESTIONS_GUEST;

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {/* Bottom-Right Launcher Icon Pill (shrinks/expands seamlessly with the window) */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Yotta Bot Assistant"
        aria-hidden={open}
        className={`ybot-launcher ybot-shell rounded-full p-1.5 pl-4 flex items-center gap-2.5 cursor-pointer ${
          open ? "scale-125 opacity-0 pointer-events-none blur-sm" : "scale-100 opacity-100 hover:scale-[1.04]"
        }`}
      >
        <div className="text-right">
          <div className="text-xs font-bold text-slate-950 dark:text-white leading-tight flex items-center justify-end gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
            <span>Yotta Bot</span>
          </div>
          <div className="text-[10px] font-medium text-slate-700 dark:text-zinc-300 leading-tight">
            Ask anything
          </div>
        </div>
        <span
          onMouseMove={trackGlassBorder}
          className="ybot-glass-icon w-10 h-10 rounded-full p-1.5 flex items-center justify-center shrink-0"
        >
          <img
            src="/yottaflex-logo.webp"
            alt="Yotta Bot"
            className="w-full h-full object-contain dark:brightness-0 dark:invert"
          />
        </span>
      </button>

      {/* Expandable Bottom-Right Overlapping Chat Window — flows directly out of & shrinks back into the icon */}
      <div
        role="dialog"
        aria-label="Yotta Bot Assistant"
        aria-hidden={!open}
        className={`ybot-window-morph ybot-shell absolute bottom-0 right-0 w-[395px] max-w-[calc(100vw-2rem)] h-[565px] max-h-[calc(100vh-2.5rem)] flex flex-col overflow-hidden ${
          open ? "ybot-window-open" : "ybot-window-closed"
        }`}
      >
        {/* 80%-Transparent Optical Glass Header */}
        <div className="px-4 py-3 border-b border-white/40 dark:border-white/18 bg-white/10 dark:bg-white/[0.02] flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2.5">
            <div
              onMouseMove={trackGlassBorder}
              className="ybot-glass-icon w-9 h-9 rounded-full p-1.5 flex items-center justify-center"
            >
              <img
                src="/yottaflex-logo.webp"
                alt="Yotta Bot"
                className="w-full h-full object-contain dark:brightness-0 dark:invert"
              />
            </div>
            <div>
              <div className="text-xs font-bold text-slate-950 dark:text-white flex items-center gap-1.5">
                <span>Yotta Bot</span>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
              </div>
              <div className="text-[10.5px] font-medium text-slate-700 dark:text-zinc-300">
                {isAuthenticated ? "Project & Live Ledger Guide" : "Sign-In & Project Guide"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onMouseMove={trackGlassBorder}
              onClick={resetChat}
              title="Reset conversation"
              className="ybot-glass-icon w-8 h-8 rounded-full flex items-center justify-center text-slate-800 dark:text-white"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onMouseMove={trackGlassBorder}
              onClick={() => setOpen(false)}
              title="Minimize back into Yotta Bot icon"
              aria-label="Minimize Yotta Bot"
              className="ybot-glass-icon w-8 h-8 rounded-full flex items-center justify-center text-slate-800 dark:text-white"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 80%-Transparent Glass Messages Area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-3.5 py-3.5 space-y-3">
          {messages.map((m) => {
            const isBot = m.role === "bot";
            return (
              <div key={m.id} className={`flex items-start gap-2 ${isBot ? "justify-start" : "justify-end"}`}>
                {isBot && (
                  <div
                    onMouseMove={trackGlassBorder}
                    className="ybot-glass-icon w-7 h-7 rounded-full p-1 flex items-center justify-center shrink-0 mt-0.5"
                  >
                    <img
                      src="/yottaflex-logo.webp"
                      alt="Yotta Bot Icon"
                      className="w-full h-full object-contain dark:brightness-0 dark:invert"
                    />
                  </div>
                )}

                <div
                  onMouseMove={trackGlassBorder}
                  className={`ybot-glass-box max-w-[82%] px-3.5 py-2.5 text-xs leading-relaxed ${
                    isBot
                      ? "rounded-2xl rounded-tl-sm text-slate-900 dark:text-zinc-100"
                      : "rounded-2xl rounded-tr-sm text-slate-950 dark:text-white"
                  }`}
                >
                  {m.source && isBot && (
                    <div className="text-[9.5px] font-mono uppercase tracking-wider text-slate-600 dark:text-zinc-400 mb-1">
                      {m.source}
                    </div>
                  )}
                  <div className="space-y-1">
                    {m.text.split("\n").map((line, i) => (
                      <div key={i}>{renderInlineText(line)}</div>
                    ))}
                  </div>

                  {m.actions && m.actions.length > 0 && onAction && isAuthenticated && (
                    <div className="mt-2 pt-2 border-t border-white/35 dark:border-white/15 flex flex-wrap gap-1.5">
                      {m.actions.map((act) => (
                        <button
                          key={`${act.type}-${act.id}`}
                          type="button"
                          onMouseMove={trackGlassBorder}
                          onClick={() => onAction(act)}
                          className="ybot-glass-box px-2.5 py-1 rounded-full text-[10.5px] font-semibold text-azure-800 dark:text-white hover:scale-[1.03] transition"
                        >
                          {act.label} →
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {!isBot && (
                  <div
                    onMouseMove={trackGlassBorder}
                    className="ybot-glass-icon w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-slate-800 dark:text-white"
                  >
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            );
          })}

          {sending && (
            <div className="flex items-center gap-2">
              <div className="ybot-glass-icon w-7 h-7 rounded-full p-1 flex items-center justify-center shrink-0">
                <img
                  src="/yottaflex-logo.webp"
                  alt=""
                  className="w-full h-full object-contain dark:brightness-0 dark:invert animate-pulse"
                />
              </div>
              <div className="ybot-glass-box rounded-2xl rounded-tl-sm px-3.5 py-2 text-xs text-slate-700 dark:text-zinc-300">
                Thinking...
              </div>
            </div>
          )}
        </div>

        {/* 80%-Transparent Quick Prompt Glass Pills */}
        <div className="px-3.5 pb-2 flex items-center gap-1.5 overflow-x-auto shrink-0">
          {prompts.map((pq) => (
            <button
              key={pq}
              type="button"
              disabled={sending}
              onMouseMove={trackGlassBorder}
              onClick={() => sendQuery(pq)}
              className="ybot-glass-box whitespace-nowrap px-3 py-1 rounded-full text-[10.5px] font-semibold text-slate-800 dark:text-zinc-100 hover:scale-[1.03] transition shrink-0"
            >
              {pq}
            </button>
          ))}
        </div>

        {/* 80%-Transparent Glass Input Box & Glass Send Icon */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendQuery();
          }}
          className="px-3.5 pb-3.5 pt-2 border-t border-white/40 dark:border-white/15 bg-white/8 dark:bg-white/[0.02] flex items-center gap-2 shrink-0"
        >
          <div onMouseMove={trackGlassBorder} className="ybot-glass-box flex-1 rounded-full flex items-center">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Yotta Bot anything..."
              className="w-full bg-transparent px-4 py-2 text-xs text-slate-950 dark:text-white placeholder:text-slate-600 dark:placeholder:text-zinc-400 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={sending || !input.trim()}
            onMouseMove={trackGlassBorder}
            aria-label="Send message to Yotta Bot"
            className="ybot-glass-icon w-9 h-9 rounded-full flex items-center justify-center text-azure-700 dark:text-white disabled:opacity-40 shrink-0"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
};
