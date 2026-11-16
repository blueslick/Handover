import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  // T97: the plain address (no patient ID) opens the Records replay first, because that is
  // the start of the story and the address shown in the demo video. The doctor screen is
  // unchanged at /?id=... (and /?view=...), so every existing link to it still works.
  // Temporary (307), so browsers never remember it for good.
  async redirects() {
    return [
      {
        source: "/",
        missing: [
          { type: "query", key: "id" },
          { type: "query", key: "view" },
        ],
        destination: "/upload",
        permanent: false,
      },
    ];
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
