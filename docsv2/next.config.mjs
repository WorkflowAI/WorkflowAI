import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/:path*',
        has: [
          {
            type: 'query',
            key: 'reader',
            value: 'ai',
          },
        ],
        destination: '/ai-reader/:path*',
      },
    ];
  },
};

export default withMDX(config);
