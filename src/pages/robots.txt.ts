import type { APIContext } from "astro";
import { SITE } from "../consts";

export function GET(context: APIContext) {
  const site = (context.site ?? new URL(SITE.url)).toString().replace(/\/$/, "");
  const body = `User-agent: *
Allow: /

Sitemap: ${site}/sitemap-index.xml
`;
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
