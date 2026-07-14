import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#f8fafc",
        line: "#cbd5e1",
        ink: "#111827",
        steel: "#334155",
        alarm: "#b91c1c",
        caution: "#b45309",
        ok: "#047857",
        control: "#0f766e"
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
} satisfies Config;
