import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

// Shared frontmatter fields across editorial content.
const base = {
  title: z.string(),
  description: z.string(),
  publishDate: z.coerce.date(),
  updatedDate: z.coerce.date().optional(),
  author: z.string().default("Dawnwalker Guide Team"),
  tags: z.array(z.string()).default([]),
  image: z.string().optional(),
  imageAlt: z.string().optional(),
  /** Optional YouTube video id to embed (lite-loaded). */
  video: z.string().optional(),
  /** Caption/title for the embedded video. */
  videoTitle: z.string().optional(),
  draft: z.boolean().default(false),
  /** Optional list of sources for transparency / E-E-A-T. */
  sources: z.array(z.object({ label: z.string(), url: z.string().url() })).default([]),
};

const news = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/news" }),
  schema: z.object({ ...base }),
});

const guides = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/guides" }),
  schema: z.object({
    ...base,
    /** guide type powers filtering + future templates. */
    category: z
      .enum([
        "overview",
        "walkthrough",
        "boss",
        "build",
        "quest",
        "endings",
        "beginner",
        "system",
        "preview",
      ])
      .default("overview"),
    /** Optional FAQ block rendered as accordion + FAQPage schema. */
    faq: z
      .array(z.object({ question: z.string(), answer: z.string() }))
      .default([]),
    /** Pillar pages are the hubs in the hub-and-spoke internal linking model. */
    pillar: z.boolean().default(false),
  }),
});

export const collections = { news, guides };
