import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";

// Flat config. High-signal correctness rules only — this is a gate meant
// to catch real bugs (undefined refs, dead bindings, hook misuse), not to
// enforce formatting. Tighten incrementally.
export default [
  {
    ignores: [
      "dist/",
      "node_modules/",
      "playwright-report/",
      "test-results/",
      ".playwright/",
    ],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Ignore intentionally-unused capitalised imports (components) and
      // args/vars prefixed with underscore.
      "no-unused-vars": [
        "error",
        { varsIgnorePattern: "^[A-Z_]", argsIgnorePattern: "^_" },
      ],
    },
  },
];
