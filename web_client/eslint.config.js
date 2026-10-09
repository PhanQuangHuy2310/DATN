import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: globals.browser,
    },
    plugins: { react, "jsx-a11y": jsxA11y, "react-hooks": reactHooks },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      ...reactHooks.configs.flat.recommended.rules,
      "react/jsx-uses-vars": "error",
      "no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "no-undef": "error",
    },
  },
  { ignores: ["dist/**"] },
];
