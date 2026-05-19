/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Cleaner build artefacts on Vercel and a smaller runtime footprint.
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  // Next typed routes require zero-arg URL strings; we use template
  // literals like `/cases/${id}/evidence`, so leave this disabled.
  experimental: {
    typedRoutes: false,
  },
  // We don't ship raster assets right now. If/when we do, declare allowed
  // remote patterns here so next/image doesn't reject them at runtime.
  images: {
    remotePatterns: [],
  },
};

export default nextConfig;
