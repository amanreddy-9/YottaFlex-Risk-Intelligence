import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Plus Jakarta Sans"',
          '"Inter"',
          "system-ui",
          "sans-serif",
        ],
        mono: [
          '"SF Mono"',
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      colors: {
        obsidian: {
          850: "#18181B",
          900: "#0D0D0F",
          950: "#050506",
          black: "#000000",
        },
        azure: {
          50: "#EEF6FF",
          100: "#D9EAFF",
          200: "#B8D9FF",
          400: "#4EA1FF",
          500: "#1D84FA",
          600: "#0A66E6",
          700: "#0950B8",
        },
      },
      boxShadow: {
        glass: "0 10px 36px rgba(15, 65, 145, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85)",
        "glass-dark": "0 14px 40px rgba(0, 0, 0, 0.72), inset 0 1px 0 rgba(255, 255, 255, 0.14)",
      },
    },
  },
  plugins: [],
} satisfies Config;
