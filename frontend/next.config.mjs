/** @type {import('next').NextConfig} */
if (typeof globalThis.localStorage !== "undefined" && typeof globalThis.localStorage.getItem !== "function") {
  delete globalThis.localStorage;
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/test-cases",
        destination: "http://127.0.0.1:8000/test-cases",
      },
      {
        source: "/analyze",
        destination: "http://127.0.0.1:8000/analyze",
      },
      {
        source: "/upload",
        destination: "http://127.0.0.1:8000/upload",
      },
      {
        source: "/audit-output",
        destination: "http://127.0.0.1:8000/audit-output",
      },
      {
        source: "/health",
        destination: "http://127.0.0.1:8000/health",
      },
    ];
  },
};

export default nextConfig;

