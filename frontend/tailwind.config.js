/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          low: "#16a34a",
          medium: "#d97706",
          high: "#dc2626",
        },
        priority: {
          critical: "#7f1d1d",
          high: "#dc2626",
          medium: "#d97706",
          low: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};
