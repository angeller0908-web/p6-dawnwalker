import rss from "@astrojs/rss";
import type { APIContext } from "astro";
import { SITE, GAME } from "../consts";
import { getNews } from "../lib/utils";

export async function GET(context: APIContext) {
  const news = await getNews();
  return rss({
    title: `${SITE.name} — ${GAME.title} News`,
    description: `Daily ${GAME.title} news, trailers, and updates.`,
    site: context.site ?? SITE.url,
    items: news.map((entry) => ({
      title: entry.data.title,
      description: entry.data.description,
      pubDate: entry.data.publishDate,
      link: `/news/${entry.id}/`,
    })),
    customData: `<language>en-us</language>`,
  });
}
