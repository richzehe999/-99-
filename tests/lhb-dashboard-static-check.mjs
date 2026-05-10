import fs from "node:fs";

const html = fs.readFileSync("a-share-lhb-dashboard.html", "utf8");

const requiredMarkers = [
  ['nav link "承接跟踪"', 'href="#follow-through"'],
  ["follow-through section", 'id="follow-through"'],
  ["next-day summary container", 'id="nextDaySummary"'],
  ["next-day table body", 'id="nextDayBody"'],
  ["seat archive matrix title", "席位历史归档矩阵"],
  ["archive review action column", "复核动作"],
  ["follow-up state bucket", "followUps"],
  ["continuation row builder", "function buildContinuationRows"],
  ["next-day tracker renderer", "function renderNextDayTracker"],
  ["continuation conclusion helper", "function continuationConclusion"]
];

const missing = requiredMarkers.filter(([, marker]) => !html.includes(marker));

if (missing.length) {
  console.error("Missing LHB dashboard markers:");
  for (const [label, marker] of missing) {
    console.error(`- ${label}: ${marker}`);
  }
  process.exit(1);
}

console.log("LHB dashboard static check ok");
