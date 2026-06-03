import { getCollection, type CollectionEntry } from "astro:content";

export function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function isoDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

const isPublished = (entry: { data: { draft: boolean } }) =>
  import.meta.env.PROD ? !entry.data.draft : true;

const byDateDesc = (
  a: { data: { publishDate: Date } },
  b: { data: { publishDate: Date } },
) => b.data.publishDate.valueOf() - a.data.publishDate.valueOf();

/** Published news, newest first. Drafts hidden in production builds. */
export async function getNews(): Promise<CollectionEntry<"news">[]> {
  const entries = await getCollection("news", isPublished);
  return entries.sort(byDateDesc);
}

/** Published guides, newest first. */
export async function getGuides(): Promise<CollectionEntry<"guides">[]> {
  const entries = await getCollection("guides", isPublished);
  return entries.sort(byDateDesc);
}
