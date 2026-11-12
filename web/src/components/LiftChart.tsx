import React from "react";
import type { EvaluationData } from "../types/workbench";

export const LiftChart: React.FC<{
  liftCurve: EvaluationData["lift_curve"];
  darkMode: boolean;
}> = ({ liftCurve, darkMode }) => {
  const W = 560;
  const H = 260;
  const pad = { l: 48, r: 22, t: 28, b: 36 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;

  const pts = [{ queue_pct: 0, priority_recall: 0, fifo_recall: 0 }, ...liftCurve];
  const xFor = (pct: number) => pad.l + (pct / 100) * plotW;
  const yFor = (rec: number) => pad.t + plotH - rec * plotH;

  const prioPath = pts.map((pt, i) => `${i === 0 ? "M" : "L"} ${xFor(pt.queue_pct)} ${yFor(pt.priority_recall)}`).join(" ");
  const fifoPath = pts.map((pt, i) => `${i === 0 ? "M" : "L"} ${xFor(pt.queue_pct)} ${yFor(pt.fifo_recall)}`).join(" ");

  const gridStroke = darkMode ? "#27272A" : "rgba(148, 192, 245, 0.45)";
  const labelFill = darkMode ? "#A1A1AA" : "#475569";
  const prioStroke = darkMode ? "#FFFFFF" : "#0A66E6";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block">
      {[0, 25, 50, 75, 100].map((p) => {
        const y = pad.t + plotH - (p / 100) * plotH;
        return (
          <g key={p}>
            <line x1={pad.l} y1={y} x2={W - pad.r} y2={y} stroke={gridStroke} strokeDasharray="3,3" />
            <text
              x={pad.l - 8}
              y={y + 4}
              textAnchor="end"
              fontSize="10"
              fontFamily="-apple-system, BlinkMacSystemFont, SF Pro Display, sans-serif"
              fill={labelFill}
            >
              {p}%
            </text>
          </g>
        );
      })}

      <path d={fifoPath} fill="none" stroke={darkMode ? "#52525B" : "#94A3B8"} strokeWidth="2.2" strokeDasharray="5,4" />
      <path d={prioPath} fill="none" stroke={prioStroke} strokeWidth="3" />

      {pts
        .filter((p) => p.queue_pct > 0)
        .map((pt) => (
          <g key={pt.queue_pct}>
            <circle cx={xFor(pt.queue_pct)} cy={yFor(pt.priority_recall)} r="4" fill={prioStroke} />
            <text
              x={xFor(pt.queue_pct)}
              y={H - 12}
              textAnchor="middle"
              fontSize="10"
              fontFamily="-apple-system, BlinkMacSystemFont, SF Pro Display, sans-serif"
              fill={labelFill}
            >
              {pt.queue_pct}%
            </text>
          </g>
        ))}

      <line x1={pad.l + 10} y1={12} x2={pad.l + 34} y2={12} stroke={prioStroke} strokeWidth="3" />
      <text x={pad.l + 40} y={16} fontSize="11" fontWeight="600" fill={darkMode ? "#FFFFFF" : "#0F172A"}>
        Risk-Prioritized Queue
      </text>

      <line x1={pad.l + 200} y1={12} x2={pad.l + 224} y2={12} stroke={darkMode ? "#52525B" : "#94A3B8"} strokeWidth="2.2" strokeDasharray="5,4" />
      <text x={pad.l + 230} y={16} fontSize="11" fill={labelFill}>
        FIFO Unranked Baseline
      </text>
    </svg>
  );
};
