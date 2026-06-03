// @ts-check
import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { SITE } from "./src/consts.ts";

// https://astro.build/config
export default defineConfig({
  site: SITE.url,
  trailingSlash: "always",
  integrations: [
    mdx(),
    sitemap({
      // Don't index the homepage less than article pages; defaults are fine.
      changefreq: "daily",
      priority: 0.7,
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
