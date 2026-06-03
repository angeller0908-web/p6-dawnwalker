// Builders for schema.org JSON-LD objects. Keep all structured data here so
// it stays consistent and is easy to validate with Google's Rich Results Test.
import { SITE, GAME } from "../consts";

const abs = (path: string) => new URL(path, SITE.url).href;

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": abs("/#organization"),
    name: SITE.name,
    url: SITE.url,
    logo: abs("/og-default.jpg"),
  };
}

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": abs("/#website"),
    url: SITE.url,
    name: SITE.name,
    description: SITE.tagline,
    publisher: { "@id": abs("/#organization") },
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: abs("/search/?q={search_term_string}"),
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function videoGameSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "VideoGame",
    name: GAME.title,
    gamePlatform: GAME.platforms,
    genre: GAME.genre,
    datePublished: GAME.releaseDate,
    author: { "@type": "Organization", name: GAME.developer },
    publisher: { "@type": "Organization", name: GAME.publisher },
    url: GAME.officialSite,
  };
}

interface ArticleInput {
  type?: "Article" | "NewsArticle";
  headline: string;
  description: string;
  url: string;
  image?: string;
  datePublished: Date;
  dateModified?: Date;
  authorName: string;
}

export function articleSchema(a: ArticleInput) {
  return {
    "@context": "https://schema.org",
    "@type": a.type ?? "Article",
    headline: a.headline,
    description: a.description,
    image: a.image ? abs(a.image) : abs(SITE.defaultImage),
    datePublished: a.datePublished.toISOString(),
    dateModified: (a.dateModified ?? a.datePublished).toISOString(),
    author: { "@type": "Person", name: a.authorName },
    publisher: { "@id": abs("/#organization") },
    mainEntityOfPage: { "@type": "WebPage", "@id": abs(a.url) },
  };
}

export function breadcrumbSchema(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: abs(item.url),
    })),
  };
}

export function faqSchema(faq: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faq.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    })),
  };
}
