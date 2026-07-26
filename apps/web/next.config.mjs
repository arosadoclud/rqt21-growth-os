/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@rqt21/contracts"],
  // Proxies /api/v1/* to the real backend (API_PROXY_TARGET, e.g. a Railway
  // URL) so the browser only ever talks to this Next.js origin. Without a
  // shared custom domain, a separately-hosted API (different origin) can't
  // reliably receive the HttpOnly session cookie back — SameSite=Lax blocks
  // it and SameSite=None is fragile against browser third-party-cookie
  // blocking (Safari ITP in particular). Routing through this same-origin
  // proxy sidesteps the problem entirely: no custom domain required. Unset
  // in local dev, where NEXT_PUBLIC_API_URL points directly at localhost.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    return [{ source: "/api/v1/:path*", destination: `${target}/api/v1/:path*` }];
  },
};

export default nextConfig;
