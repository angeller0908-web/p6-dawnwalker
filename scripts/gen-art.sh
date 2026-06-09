#!/bin/sh
# Generate original dark-fantasy art for each article via the agy CLI.
# Resumable: skips any slug whose raw file already exists.
# Usage: sh scripts/gen-art.sh
set -u

AGY=/Users/Angel-Tong/.local/bin/agy
ROOT=/Users/Angel-Tong/p6-dawnwalker
RAW="$ROOT/art-src"
mkdir -p "$RAW"

# Shared style anchor appended to every prompt for a consistent look.
STYLE="Original dark-fantasy oil painting, 14th-century Eastern-European gothic mood, cinematic and painterly, muted palette with blood-red and dawn-gold accents, atmospheric fog and dramatic light. No text, no logos, no watermarks, no UI, no modern objects, no recognizable real people."

gen() {
  slug="$1"
  scene="$2"
  out="$RAW/$slug.png"
  if [ -s "$out" ]; then
    echo "SKIP  $slug (exists)"
    return 0
  fi
  echo "GEN   $slug ..."
  "$AGY" --dangerously-skip-permissions --print-timeout 4m \
    --prompt="Generate an image. $scene $STYLE Save the generated image as a PNG file to the absolute path $out" \
    >"$RAW/$slug.log" 2>&1
  if [ -s "$out" ]; then
    echo "OK    $slug"
  else
    echo "FAIL  $slug (see $RAW/$slug.log)"
  fi
}

# ---- Article scenes ----
gen "everything-we-know"            "A lone hooded wanderer on a misty mountain pass at blood-red dawn, a distant gothic castle silhouette perched on a crag, wide establishing shot."
gen "release-date-platforms-editions" "An ornate ancient leather tome with wax seals beside a hand-drawn parchment map of a mountain valley and an engraved steel dagger on a dark oak table, warm candlelight."
gen "gameplay-systems-explained"    "A dramatic split landscape: the left half a warm sunlit medieval mountain village by day, the right half the same valley under a cold blue moon with mist and circling bats by night, a lone figure standing at the dividing line."
gen "story-setting-characters"      "A grim medieval Carpathian mountain village at dusk beneath a blood-red moon, crooked wooden houses, lantern light, thick fog rolling through narrow lanes."
gen "pc-system-requirements"        "A candlelit alchemist's study with glowing arcane runes, a brass mechanical orrery, scattered parchment diagrams and quills on a heavy wooden desk."
gen "30-day-time-limit-explained"   "A large ornate hourglass filled with glowing blood-red sand on a carved gothic stone table, cold moonlight through a tall arched window."
gen "brencis-and-vampire-officers"  "A vast shadowy gothic throne room with a towering empty vampiric throne, faceless cloaked silhouettes in the gloom, tattered crimson banners, dramatic shafts of red light."
gen "infamy-system-explained"       "A torchlit medieval town square at night, a weathered notice nailed to a wooden post, distant silhouettes of armored guards, tense uneasy atmosphere."
gen "romance-guide"                 "Two cloaked silhouettes facing each other by warm candlelight in an intimate gothic stone chamber, dark red roses and soft shadow, romantic and somber."
gen "vs-the-witcher-3"              "Two diverging paths in a dark misty forest at twilight, one path bathed in warm dawn light and the other in cold blue moonlight, an old wooden signpost at the fork."
gen "beginner-tips-before-you-play" "A lantern-lit crossroads at the edge of a dark pine forest at dawn, a traveler's leather pack and a worn walking staff resting against a stone marker, inviting mood."
gen "how-long-to-beat"              "A weathered hourglass beside a worn leather traveler's journal and a quill on a candlelit wooden table, intimate still life."
gen "single-player-or-multiplayer" "A single solitary cloaked figure walking a lonely moonlit road through a vast empty misty valley, sense of solitude."
gen "vampire-powers-and-wolf-form" "A large spectral black wolf with faintly glowing eyes prowling through a moonlit gothic ruin amid drifting mist."
gen "combat-and-hex-magic"         "A medieval swordsman mid-parry with his blade raised, crackling crimson hex energy swirling around the steel, dynamic and dramatic."
gen "builds-and-skill-trees"       "An ornate branching tree-like diagram etched in glowing amber runes on dark aged parchment beside a burning candle and an inkwell."
gen "vale-sangora-world-guide"     "A sweeping panoramic vista over a fog-filled Carpathian valley with scattered tiny medieval villages and a distant castle on a ridge at dusk."

# ---- News scenes ----
gen "launch-date-september-3-confirmed" "A triumphant blood-red dawn breaking over a vast gothic mountain valley, golden rays piercing the mist, a castle silhouette catching the first light."
gen "how-choice-driven-is-dawnwalker"   "A single cloaked figure standing at a fork where two roads split beneath a dramatic divided sky, warm daylight on one side and starlit night on the other."

# ---- Character key art (original, NOT the game's character designs) ----
gen "coen-portrait"    "Cinematic character key art of a brooding young medieval peasant man in a weathered hooded cloak, three-quarter view, half his face lit by warm dawn light and half in cold blue shadow, faint pale silver scarring at his throat, standing on a misty mountainside at blood-red dawn, an original character not based on any existing game."
gen "brencis-portrait" "Cinematic character key art of an ancient aristocratic vampire lord with gaunt pale features and piercing cold eyes, wearing ornate dark Roman-influenced gothic regalia, seated upon a shadowy carved throne in a candlelit hall, regal and menacing, dramatic crimson rim light, an original character not based on any existing game."

# ---- Tools: parchment map for the interactive-map teaser ----
gen "vale-sangora-map" "An aged hand-drawn antique parchment map of a fog-shrouded Carpathian mountain valley seen from above, ink-drawn forests, winding rivers, tiny medieval village icons and a castle marked on a crag, a decorative compass rose and ornate border, weathered and stained vellum, painted cartographic style."

# ---- Site-wide ----
gen "hero"        "An epic wide cinematic vista of a vast Carpathian valley at blood-red dawn, a great gothic castle on a distant crag, layers of mist and jagged pine ridges, very dark and atmospheric with deep shadow at the top and bottom edges."
gen "og-base"     "An epic wide cinematic vista of a gothic mountain valley at blood-red dawn with a distant castle and dramatic god rays through mist, dark moody composition with empty darker space in the lower third."

echo "ALL DONE"
