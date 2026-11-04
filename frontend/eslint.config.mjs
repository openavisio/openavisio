import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // CI gates on errors (#379). These stay visible as warnings: `any` until it is
    // cleaned up, and the React Compiler rules because the app does not use the
    // compiler and every hit (mount-time effects, a server component's fetch flag,
    // Date.now for an age) was checked and is intended.
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
    },
  },
  {
    // Calls that skip backendFetch drop the visitor's IP, and every visitor then shares
    // one per-IP budget. auth.ts cannot use it (backendFetch calls auth()); the proxy
    // and the cached locale lookup forward or need none, the next.config rewrite forwards itself.
    ignores: ["src/lib/backend.ts", "src/auth.ts", "src/proxy.ts", "src/i18n/request.ts", "next.config.ts"],
    rules: {
      "no-restricted-syntax": ["error", {
        selector: "MemberExpression[object.object.name='process'][object.property.name='env'][property.name='API_URL']",
        message: "Call the backend through backendFetch() from @/lib/backend.",
      }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
