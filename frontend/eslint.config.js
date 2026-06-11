import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default [
  { ignores: ['dist', 'node_modules', 'playwright-report', 'test-results'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // The compiler-powered diagnostics added in react-hooks v6+
      // flag long-standing fetch-on-mount patterns across the app.
      // Baseline with the classic rules (rules-of-hooks /
      // exhaustive-deps); revisit when adopting the React compiler.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/immutability': 'off',
      'react-refresh/only-export-components': 'warn',
      // JSX usage counts as a read; the base rule can't see it
      // without the full react plugin, so scope to vars that are
      // provably unused and skip all-caps constants kept for docs.
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      // Empty catch with a comment is the codebase's established
      // "best-effort, failure tolerated" idiom (store prefetches,
      // logout). New code should still log — see CLAUDE.md §2.1.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // Playwright fixtures take a `use` callback that the React
    // hooks plugin misreads as a hook call.
    files: ['tests/**/*.js'],
    rules: {
      'react-hooks/rules-of-hooks': 'off',
    },
  },
]
