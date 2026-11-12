import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Local dev proxies to the API on the reserved backend port. In containerised
// environments (e.g. the Docker web service) this can be overridden with
//   VITE_API_PROXY_TARGET=http://api:16901
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET || "http://127.0.0.1:16901";

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 16900,
      strictPort: true,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: "0.0.0.0",
      port: 16900,
      strictPort: true,
    },
  };
});
