/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${API_URL}/:path*` },
    ];
  },
};
module.exports = nextConfig;
