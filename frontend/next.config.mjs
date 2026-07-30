/** @type {import('next').NextConfig} */

// Proxy same-origin: browser memanggil `/api/*` (asal sama dgn halaman), lalu
// server Next meneruskannya ke backend di jaringan Docker. Dengan ini cukup SATU
// tunnel (port 3000) untuk demo publik (Cloudflare Tunnel) — tak perlu ekspos
// backend terpisah, dan tak perlu CORS. Set NEXT_PUBLIC_API_BASE=/api agar klien
// memakai jalur ini.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "http://api:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` }];
  },
};

export default nextConfig;
