import sharedConfig from "../../next.config.mjs";

const nextConfig = {
  ...sharedConfig,
  experimental: {
    ...sharedConfig.experimental,
    externalDir: true,
  },
};

export default nextConfig;