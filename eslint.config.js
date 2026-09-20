import globals from "globals";

export default [
  {
    files: ["frontend/assets/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.browser },
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "error",
      eqeqeq: ["error", "smart"],
      "prefer-const": "error",
    },
  },
];
