import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "1360px" },
    },
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0F1419",
          soft: "#22303C",
          mute: "#6B7280",
          faint: "#9AA3AD",
        },
        parchment: {
          DEFAULT: "#F6F2E9",
          soft: "#FBF8F1",
        },
        card: "#FFFFFF",
        rule: {
          DEFAULT: "#E4DDCC",
          soft: "#EFE9DA",
        },
        accent: {
          DEFAULT: "#7A4A1F",
          soft: "#A47650",
          wash: "#F1E6D6",
        },
        seal: "#7B1E3A",
        success: { DEFAULT: "#2F5233", wash: "#E6EDE5" },
        warning: { DEFAULT: "#9A6B12", wash: "#F4EAD0" },
        danger: { DEFAULT: "#7B1E3A", wash: "#F1DCE2" },
      },
      fontFamily: {
        display: [
          "var(--font-display)",
          '"Fraunces"',
          '"Cormorant Garamond"',
          "Georgia",
          "serif",
        ],
        body: [
          "var(--font-body)",
          '"IBM Plex Sans"',
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          '"IBM Plex Mono"',
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        lg: "10px",
        md: "8px",
        sm: "6px",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 200ms ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
