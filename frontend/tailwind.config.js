/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#000000",
        surface: "#0a0a0a",
        border: "#222222",
        muted: "#666666",
        accent: "#ffffff",
        "glow-white": "rgba(255,255,255,0.08)",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,255,255,0.15), 0 0 20px rgba(255,255,255,0.06)",
        "glow-active": "0 0 0 1px rgba(255,255,255,0.4), 0 0 24px rgba(255,255,255,0.12)",
      },
    },
  },
  plugins: [],
};
