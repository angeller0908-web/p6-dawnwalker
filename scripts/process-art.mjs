// Post-process raw generated art into optimized, correctly-sized web images.
// Crops the square renders to 16:9, compresses for fast LCP, and builds the
// homepage hero + a painted OG share image with the title overlaid.
// Run: node scripts/process-art.mjs   (safe to re-run; skips missing raws)
import sharp from "sharp";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { existsSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUB = join(__dirname, "..", "public");
const RAW = join(__dirname, "..", "art-src");
const OUT = join(PUB, "images");

const articleSlugs = [
  "everything-we-know",
  "release-date-platforms-editions",
  "gameplay-systems-explained",
  "story-setting-characters",
  "pc-system-requirements",
  "30-day-time-limit-explained",
  "brencis-and-vampire-officers",
  "infamy-system-explained",
  "romance-guide",
  "vs-the-witcher-3",
  "beginner-tips-before-you-play",
  "how-long-to-beat",
  "single-player-or-multiplayer",
  "vampire-powers-and-wolf-form",
  "combat-and-hex-magic",
  "builds-and-skill-trees",
  "vale-sangora-world-guide",
  "launch-date-september-3-confirmed",
  "how-choice-driven-is-dawnwalker",
];

const raw = (slug) => join(RAW, `${slug}.png`);
let done = 0;
let missing = [];

// 16:9 article images (cards + article heroes).
for (const slug of articleSlugs) {
  const src = raw(slug);
  if (!existsSync(src)) {
    missing.push(slug);
    continue;
  }
  await sharp(src)
    .resize(1600, 900, { fit: "cover", position: "attention" })
    .jpeg({ quality: 78, mozjpeg: true })
    .toFile(join(OUT, `${slug}.jpg`));
  done++;
}

// Homepage hero — wider, slightly darkened for text legibility.
if (existsSync(raw("hero"))) {
  await sharp(raw("hero"))
    .resize(2000, 1100, { fit: "cover", position: "attention" })
    .modulate({ brightness: 0.82 })
    .jpeg({ quality: 80, mozjpeg: true })
    .toFile(join(OUT, "hero.jpg"));
  done++;
} else {
  missing.push("hero");
}

// Painted OG share image (1200x630) with title + dark scrim for readability.
const ogSrc = existsSync(raw("og-base"))
  ? raw("og-base")
  : existsSync(raw("hero"))
    ? raw("hero")
    : null;
if (ogSrc) {
  const W = 1200;
  const H = 630;
  const overlay = Buffer.from(`
<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgba(11,10,15,0.15)"/>
      <stop offset="60%" stop-color="rgba(11,10,15,0.45)"/>
      <stop offset="100%" stop-color="rgba(11,10,15,0.92)"/>
    </linearGradient>
    <linearGradient id="dawn" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#e8a33d"/>
      <stop offset="100%" stop-color="#e23645"/>
    </linearGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#scrim)"/>
  <rect x="0" y="0" width="${W}" height="6" fill="url(#dawn)"/>
  <text x="60" y="500" font-family="Georgia, 'Times New Roman', serif" font-weight="700" font-size="64" fill="#ece6da">The Blood of Dawnwalker</text>
  <text x="62" y="548" font-family="Arial, Helvetica, sans-serif" font-size="26" fill="#e8a33d" letter-spacing="2">Guides &#183; Walkthroughs &#183; Builds &#183; Daily News</text>
</svg>`);
  await sharp(ogSrc)
    .resize(W, H, { fit: "cover", position: "attention" })
    .composite([{ input: overlay, top: 0, left: 0 }])
    .jpeg({ quality: 85, mozjpeg: true })
    .toFile(join(PUB, "og-default.jpg"));
  done++;
}

console.log(`Processed ${done} image(s).`);
if (missing.length) {
  console.log(`Still missing raws (skipped): ${missing.join(", ")}`);
}
