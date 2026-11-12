import React from "react";

type Variant = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "BLUE" | "NEUTRAL";

const STYLES: Record<Variant, string> = {
  CRITICAL: "badge-glass badge-glass-critical",
  HIGH: "badge-glass badge-glass-high",
  MEDIUM: "badge-glass badge-glass-medium",
  LOW: "badge-glass badge-glass-low",
  BLUE: "badge-glass badge-glass-blue",
  NEUTRAL: "badge-glass badge-glass-neutral",
};

export function tierVariant(tier: string): Variant {
  if (tier === "CRITICAL" || tier === "HIGH" || tier === "MEDIUM" || tier === "LOW") return tier;
  return "NEUTRAL";
}

export function statusVariant(status: string): Variant {
  if (status === "ESCALATED" || status === "SAR_FILED" || status === "CLOSED_CONFIRMED_FRAUD") return "CRITICAL";
  if (status === "IN_REVIEW") return "HIGH";
  if (status === "OPEN") return "BLUE";
  if (status === "GROUPED" || status === "CLOSED_FALSE_POSITIVE" || status === "ACKNOWLEDGED" || status === "RESOLVED") return "LOW";
  return "LOW";
}

export const Badge: React.FC<{ variant?: Variant; children: React.ReactNode; className?: string }> = ({
  variant = "NEUTRAL",
  children,
  className = "",
}) => (
  <span
    className={`inline-flex items-center px-2 py-[1.5px] rounded-full text-[9px] leading-[1.25] font-bold tracking-wider uppercase whitespace-nowrap ${STYLES[variant]} ${className}`}
  >
    {children}
  </span>
);

export const fmtUSD = (val: number | undefined | null): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(val || 0));

/**
 * Renders iOS-style currency numbers matching Reference Images 1 & 2:
 * crisp SF Display integer digits + slightly lighter, translucent decimal fraction.
 */
export const IosAmount: React.FC<{
  value: number | undefined | null;
  className?: string;
  showPlus?: boolean;
}> = ({ value, className = "", showPlus = false }) => {
  const num = Number(value || 0);
  const abs = Math.abs(num);
  const [whole, dec] = abs.toFixed(2).split(".");
  const grouped = Number(whole).toLocaleString("en-US");
  const sign = num < 0 ? "-" : showPlus ? "+" : "";
  return (
    <span className={`ios-num inline-flex items-baseline ${className}`}>
      <span>
        {sign}${grouped}
      </span>
      <span className="opacity-65 text-[0.76em] font-medium">.{dec}</span>
    </span>
  );
};
