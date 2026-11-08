import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";
import { applyPresentationChartFont } from "/Users/_d-one_/.codex/plugins/cache/openai-primary-runtime/presentations/26.1030.10813/skills/presentations/container_tools/artifact_tool_utils.mjs";

const ROOT = "/Users/_d-one_/Desktop/Thesis";
const OUT = path.join(ROOT, "Supervisor Presentation");
const BUILD = path.join(OUT, ".build");
const PREVIEWS = path.join(BUILD, "previews");
const FONT = "Kohinoor Bangla";
const MATH_FONT = "STIX Two Math";
const W = 1280;
const H = 720;

const C = {
  navy: "#12355B",
  navy2: "#0B2545",
  teal: "#0F766E",
  tealLight: "#DDF4EF",
  blue: "#2563EB",
  blueLight: "#EAF2FF",
  orange: "#F97316",
  orangeLight: "#FFF1E8",
  green: "#16A34A",
  greenLight: "#E8F7EC",
  red: "#DC2626",
  redLight: "#FDECEC",
  ink: "#172033",
  slate: "#475569",
  muted: "#64748B",
  line: "#D7E1EC",
  pale: "#F8FAFC",
  white: "#FFFFFF",
};

const IMG = {
  duLayout: path.join(ROOT, "Simulation/results/du_outdoor_layout_capture.png"),
  duDamage: path.join(ROOT, "Simulation/results/du_outdoor_damage_capture.png"),
  synthetic: path.join(ROOT, "Simulation/results/synthetic_map_capture.png"),
  heiData: path.join(ROOT, "Simulation/results/heidata_geospatial_overview.png"),
};

const DEMO = {
  syntheticLayout: path.join(ROOT, "Simulation/results/synthetic_environment/02_synthetic_building_layout_3d.html"),
  syntheticDamage: path.join(ROOT, "Simulation/results/synthetic_environment/03_synthetic_damage_moderate.html"),
  syntheticOperational: path.join(ROOT, "Simulation/results/synthetic_environment/04_synthetic_operational_environment.html"),
  duLayout: path.join(ROOT, "Simulation/results/du_environment/02_du_building_layout_3d.html"),
  duDamage: path.join(ROOT, "Simulation/results/du_environment/03_du_damage_moderate.html"),
  duOperational: path.join(ROOT, "Simulation/results/du_environment/04_du_operational_environment.html"),
  heiDataPair: path.join(ROOT, "Simulation/results/heidata_source_pair.html"),
  heiDataBenchmark: path.join(ROOT, "Simulation/results/heidata_geospatial_benchmark.html"),
  v1: path.join(ROOT, "Simulation/results/pgbm_v1_two_hour_experiments/visualizations/initial_solution_snapshot_2026-09-27/du_outdoor_initial_solution_step_by_step_replay.html"),
  v2: path.join(ROOT, "Simulation/results/pgbm_v2_recourse_demo/du_outdoor_seed102_v2_recourse_demo.html"),
  v1Report: path.join(ROOT, "Experiment Reports/V1/pgbm_v1_simulation_findings_bn.pdf"),
  v2Report: path.join(ROOT, "Experiment Reports/V2/pgbm_v2_comparative_findings_bn.pdf"),
  v21Report: path.join(ROOT, "Experiment Reports/V2.1/pgbm_v2_1_cache_aware_findings_bn.pdf"),
};

function pos(left, top, width, height) { return { left, top, width, height }; }
function localUrl(filePath) {
  const relative = path.relative(ROOT, filePath).split(path.sep).map(encodeURIComponent).join("/");
  return `http://localhost:8765/${relative}`;
}

async function imageBlob(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function addText(slide, text, box, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: box,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: 20,
    color: C.ink,
    verticalAlignment: "middle",
    autoFit: "shrinkText",
    ...style,
  };
  return shape;
}

function addMathText(slide, text, box, style = {}) {
  return addText(slide, text, box, { typeface: MATH_FONT, ...style });
}

function addRichText(slide, paragraphs, box, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: box,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text.set(paragraphs);
  shape.text.style = {
    typeface: FONT,
    fontSize: 18,
    color: C.ink,
    verticalAlignment: "middle",
    autoFit: "shrinkText",
    ...style,
  };
  return shape;
}

function addRect(slide, box, fill, radius = "rounded-lg", lineFill = fill) {
  const config = {
    geometry: radius === "none" ? "rect" : "roundRect",
    position: box,
    fill,
    line: { style: "solid", fill: lineFill, width: 1 },
  };
  if (radius !== "none") config.borderRadius = radius;
  return slide.shapes.add(config);
}

function addLine(slide, x, y, width, color = C.line, height = 2) {
  return slide.shapes.add({
    geometry: "rect",
    position: pos(x, y, width, height),
    fill: color,
    line: { style: "solid", fill: color, width: 0 },
  });
}

function addTitle(slide, kicker, title, subtitle = "") {
  addText(slide, kicker.toUpperCase(), pos(68, 32, 560, 22), {
    fontSize: 12, bold: true, color: C.teal, letterSpacing: 1.2,
  });
  addText(slide, title, pos(68, 58, 1110, 52), {
    fontSize: 31, bold: true, color: C.navy2,
  });
  if (subtitle) addText(slide, subtitle, pos(70, 111, 1120, 28), { fontSize: 15, color: C.muted });
  addLine(slide, 68, 145, 1144, C.line, 1);
}

function addFooter(slide, number) {
  addLine(slide, 68, 686, 1144, C.line, 1);
  addText(slide, "PGBM Thesis  |  Supervisor update  |  04 Nov 2026", pos(68, 692, 500, 17), {
    fontSize: 10, color: C.muted,
  });
  addText(slide, String(number).padStart(2, "0"), pos(1160, 690, 52, 20), {
    fontSize: 12, bold: true, color: C.navy, alignment: "right",
  });
}

function addChip(slide, label, value, box, accent = C.navy, fill = C.white) {
  addRect(slide, box, fill, "rounded-xl", C.line);
  addText(slide, value, pos(box.left + 14, box.top + 9, box.width - 28, 29), {
    fontSize: 24, bold: true, color: accent, alignment: "center",
  });
  addText(slide, label, pos(box.left + 10, box.top + 39, box.width - 20, 22), {
    fontSize: 12, color: C.slate, alignment: "center",
  });
}

function addBulletList(slide, items, box, fontSize = 18, color = C.ink) {
  const paragraphs = items.map((item) => ({
    bulletCharacter: "•",
    marginLeft: Math.round(18 * 12700),
    indent: -Math.round(9 * 12700),
    spaceAfter: Math.round(8 * 100),
    runs: [{ run: item }],
  }));
  return addRichText(slide, paragraphs, box, { fontSize, color, lineSpacing: 1.08 });
}

function addLinkList(slide, links, box, fontSize = 17) {
  const paragraphs = links.map(({ label, path: target }) => ({
    bulletCharacter: "↗",
    marginLeft: Math.round(18 * 12700),
    indent: -Math.round(9 * 12700),
    spaceAfter: Math.round(8 * 100),
    runs: [{
      run: label,
      style: { underline: "sng", color: C.blue, typeface: FONT },
      link: { uri: localUrl(target), isExternal: true },
    }],
  }));
  return addRichText(slide, paragraphs, box, { fontSize, color: C.blue, autoFit: "none" });
}

async function addImage(slide, filePath, box, alt, fit = "contain") {
  slide.images.add({
    blob: await imageBlob(filePath),
    contentType: "image/png",
    alt,
    fit,
    position: box,
    geometry: "roundRect",
    borderRadius: "rounded-xl",
  });
}

function addChart(slide, type, config) {
  const chart = slide.charts.add(type, {
    ...config,
    chartFill: C.white,
    chartLine: { style: "solid", fill: C.line, width: 1 },
    plotAreaFill: C.white,
    plotAreaLine: { style: "solid", fill: C.white, width: 0 },
    titlePlacement: "none",
  });
  try { applyPresentationChartFont(chart, { fontFamily: FONT }); } catch (_) { /* finalizer applies the font policy */ }
  return chart;
}

function setNotes(slide, text) {
  slide.speakerNotes.text = text;
  slide.speakerNotes.setVisible(true);
}

function addTag(slide, text, box, fill = C.blueLight, color = C.navy) {
  addRect(slide, box, fill, "rounded-xl", fill);
  addText(slide, text, box, { fontSize: 13, bold: true, color, alignment: "center" });
}

async function build() {
  const deck = Presentation.create({ slideSize: { width: W, height: H } });

  // Slide 1 — title
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addRect(s, pos(0, 0, 1280, 720), C.pale, "none", C.pale);
    addRect(s, pos(0, 0, 22, 720), C.teal, "none", C.teal);
    addText(s, "PGBM THESIS", pos(78, 82, 410, 28), { fontSize: 15, bold: true, color: C.teal, letterSpacing: 1.5 });
    addText(s, "Work Completed After\nProblem Formulation", pos(78, 142, 745, 156), { fontSize: 46, bold: true, color: C.navy2, lineSpacing: 0.94 });
    addText(s, "Simulation pipeline • V1 baseline • V2 recourse • V2.1 cache-aware planning", pos(82, 332, 730, 42), { fontSize: 20, color: C.slate });
    addLine(s, 82, 406, 170, C.orange, 5);
    addText(s, "Supervisor progress update", pos(82, 438, 430, 32), { fontSize: 20, bold: true, color: C.ink });
    addText(s, "04 November 2026", pos(82, 478, 330, 28), { fontSize: 15, color: C.muted });
    addRect(s, pos(855, 96, 320, 440), C.navy, "rounded-2xl", C.navy);
    addText(s, "FORMULATION", pos(895, 145, 230, 22), { fontSize: 13, bold: true, color: "#A7F3D0", alignment: "center" });
    addText(s, "→", pos(980, 190, 70, 50), { fontSize: 38, bold: true, color: C.orange, alignment: "center" });
    addText(s, "SIMULATION", pos(895, 254, 230, 22), { fontSize: 13, bold: true, color: "#BFDBFE", alignment: "center" });
    addText(s, "→", pos(980, 299, 70, 50), { fontSize: 38, bold: true, color: C.orange, alignment: "center" });
    addText(s, "EVIDENCE", pos(895, 363, 230, 22), { fontSize: 13, bold: true, color: "#FED7AA", alignment: "center" });
    addText(s, "V1  •  V2  •  V2.1", pos(884, 435, 260, 28), { fontSize: 18, bold: true, color: C.white, alignment: "center" });
    addText(s, "English presentation with technical notation", pos(82, 665, 600, 20), { fontSize: 11, color: C.muted });
    setNotes(s, "This presentation summarizes the work completed after problem formulation. The narrative moves from the formulation summary to the simulation pipeline, then to V1 baseline evidence, V2 recourse, and V2.1 cache-aware planning.");
  }

  // Slide 2 — problem formulation summary
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "01 / Problem formulation", "Problem formulation summary", "The planner values timely service while preserving physical feasibility and safe return.");
    addRect(s, pos(70, 178, 1140, 150), C.white, "rounded-2xl", C.line);
    addTag(s, "PROBLEM STATEMENT", pos(95, 201, 175, 26), C.orangeLight, "#9A3412");
    addText(s, "Design a multi-UAV disaster-response delivery planner that maximizes time-sensitive service value under dynamic arrivals, blocked routes, payload limits, energy reserve, return-to-base requirements, and a finite operating horizon.", pos(95, 245, 1065, 56), { fontSize: 18, color: C.ink, lineSpacing: 1.05 });
    addRect(s, pos(70, 355, 700, 190), C.navy, "rounded-2xl", C.navy);
    addTag(s, "PRIMARY OBJECTIVE", pos(95, 380, 170, 26), "#173E69", "#BFDBFE");
    addMathText(s, "max", pos(118, 425, 70, 30), { fontSize: 25, bold: true, color: C.white, alignment: "center" });
    addMathText(s, "π ∈ Π", pos(112, 456, 82, 20), { fontSize: 13, color: "#BFDBFE", alignment: "center" });
    addMathText(s, "J(π) =", pos(205, 430, 150, 34), { fontSize: 24, bold: true, color: C.white, alignment: "center" });
    addMathText(s, "Σ", pos(365, 418, 55, 45), { fontSize: 36, bold: true, color: C.white, alignment: "center" });
    addMathText(s, "i ∈ T_served", pos(350, 457, 100, 20), { fontSize: 12, color: "#BFDBFE", alignment: "center" });
    addMathText(s, "sᵢ exp[−λ(Cᵢ − tᵢ)]", pos(440, 430, 285, 34), { fontSize: 23, bold: true, color: C.white, alignment: "center" });
    addText(s, "subject to", pos(108, 495, 82, 20), { fontSize: 12, bold: true, color: "#A7F3D0" });
    addMathText(s, "xᵢᵤ ∈ {0,1}   mᵤ ≤ Mᵤ   Eᵤ ≤ Eᵤᵐᵃˣ   rᵤ ∩ O = ∅   Cᵢ ≤ H", pos(190, 493, 535, 23), { fontSize: 12, color: "#CBD5E1" });
    addRect(s, pos(800, 355, 410, 190), C.white, "rounded-2xl", C.line);
    addTag(s, "RECOURSE RULE", pos(825, 380, 125, 26), C.tealLight, C.teal);
    addText(s, "At a trigger, evaluate one-for-one replacement of an uncompleted task.", pos(825, 425, 355, 42), { fontSize: 17, color: C.ink });
    addText(s, "Accept only if feasible and ΔJ = Jnew − Jold > 0. Completed route prefix remains fixed; the displaced task returns to the queue.", pos(825, 482, 355, 45), { fontSize: 15, color: C.slate });
    addChip(s, "service value", "time-sensitive", pos(70, 580, 230, 60), C.teal, C.tealLight);
    addChip(s, "feasibility", "hard constraints", pos(320, 580, 230, 60), C.blue, C.blueLight);
    addChip(s, "recourse", "positive ΔJ only", pos(570, 580, 230, 60), C.orange, C.orangeLight);
    addChip(s, "next", "simulation evidence", pos(820, 580, 250, 60), C.navy, C.white);
    addFooter(s, 2);
    setNotes(s, "This slide gives the formulation before showing implementation evidence. The primary objective is the sum of completion-time-decayed service values. Payload, energy, collision-free routing, safe return, and the finite horizon define feasibility. Recourse evaluates a one-for-one replacement and accepts it only when the feasible plan improves J.");
  }

  // Slide 3 — pipeline
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "02 / From formulation to execution", "From formulation to the simulation pipeline", "Each stage produces the inputs required by the next stage, keeping the experiment reproducible.");
    const xs = [75, 292, 509, 726, 943];
    const labels = [
      ["OBJECTIVE", "service value\n+ energy cost", C.navy, C.blueLight],
      ["ASSIGNMENT", "UAV ↔ task\nfeasibility", C.teal, C.tealLight],
      ["ROUTING", "bounded joint\nroute plan", C.orange, C.orangeLight],
      ["PAYLOAD", "mass + volume\nconstraints", C.blue, C.blueLight],
      ["ENERGY", "flight + return\nhorizon guard", C.green, C.greenLight],
    ];
    labels.forEach(([head, body, color, fill], i) => {
      addRect(s, pos(xs[i], 220, 180, 150), fill, "rounded-2xl", fill);
      addText(s, String(i + 1).padStart(2, "0"), pos(xs[i] + 18, 238, 35, 24), { fontSize: 12, bold: true, color });
      addText(s, head, pos(xs[i] + 18, 270, 145, 22), { fontSize: 15, bold: true, color });
      addText(s, body, pos(xs[i] + 18, 305, 145, 48), { fontSize: 17, color: C.ink });
      if (i < 4) addText(s, "→", pos(xs[i] + 183, 278, 32, 32), { fontSize: 26, bold: true, color: C.muted, alignment: "center" });
    });
    addRect(s, pos(150, 430, 980, 110), C.white, "rounded-2xl", C.line);
    addText(s, "Service value calibration", pos(180, 455, 250, 26), { fontSize: 16, bold: true, color: C.navy });
    addText(s, "vᵢ(Cᵢ) = sᵢ e⁻ˡᵃᵐᵇᵈᵃ⁽ᶜⁱ⁻ᵗⁱ⁾", pos(465, 447, 350, 38), { fontSize: 25, bold: true, color: C.teal, alignment: "center" });
    addText(s, "Exponential model preserved severity ordering; lowest reported MSE ≈ 0.000892.", pos(835, 455, 260, 38), { fontSize: 13, color: C.slate });
    addText(s, "Experiment output: trace + metrics + replayable HTML evidence", pos(190, 582, 900, 28), { fontSize: 20, bold: true, color: C.navy2, alignment: "center" });
    addFooter(s, 3);
    setNotes(s, "This slide connects the mathematical formulation to the executable pipeline. The simulator evaluates assignment, collision-aware routing, payload, energy, return, and horizon feasibility before comparing candidate plans by service value.");
  }

  // Slide 4 — environments and links
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "03 / Simulation environments", "Environment evidence and clickable demos", "The same planner is evaluated against synthetic, DU outdoor, and heiDATA reference assets.");
    await addImage(s, IMG.synthetic, pos(70, 178, 325, 190), "Synthetic operational map", "cover");
    await addImage(s, IMG.duDamage, pos(430, 178, 325, 190), "DU outdoor damage map", "cover");
    await addImage(s, IMG.heiData, pos(790, 178, 380, 190), "heiDATA geospatial reference", "contain");
    addTag(s, "SYNTHETIC", pos(85, 382, 116, 24), C.blueLight, C.blue);
    addTag(s, "DU OUTDOOR", pos(445, 382, 125, 24), C.orangeLight, "#C2410C");
    addTag(s, "heiDATA REFERENCE", pos(805, 382, 165, 24), C.tealLight, C.teal);
    addText(s, "controlled geometry + damage", pos(85, 412, 290, 22), { fontSize: 13, color: C.slate });
    addText(s, "OSM-derived layout + synthetic damage", pos(445, 412, 300, 22), { fontSize: 13, color: C.slate });
    addText(s, "source mesh / geospatial benchmark", pos(805, 412, 320, 22), { fontSize: 13, color: C.slate });
    addRect(s, pos(70, 458, 1100, 202), C.white, "rounded-2xl", C.line);
    addText(s, "OPEN ENVIRONMENT DEMOS", pos(95, 477, 240, 22), { fontSize: 13, bold: true, color: C.teal });
    addText(s, "SYNTHETIC", pos(95, 505, 250, 20), { fontSize: 14, bold: true, color: C.blue });
    addLinkList(s, [
      { label: "3D building layout", path: DEMO.syntheticLayout },
      { label: "Moderate damage", path: DEMO.syntheticDamage },
      { label: "Operational environment", path: DEMO.syntheticOperational },
    ], pos(95, 528, 285, 112), 14);
    addText(s, "DU OUTDOOR", pos(420, 505, 250, 20), { fontSize: 14, bold: true, color: "#C2410C" });
    addLinkList(s, [
      { label: "3D building layout", path: DEMO.duLayout },
      { label: "Moderate damage", path: DEMO.duDamage },
      { label: "Operational environment", path: DEMO.duOperational },
    ], pos(420, 528, 285, 112), 14);
    addText(s, "heiDATA REFERENCE", pos(745, 505, 280, 20), { fontSize: 14, bold: true, color: C.teal });
    addLinkList(s, [
      { label: "Source pair", path: DEMO.heiDataPair },
      { label: "Geospatial benchmark", path: DEMO.heiDataBenchmark },
    ], pos(745, 528, 360, 70), 14);
    addText(s, "Start the local demo server before presenting: http://localhost:8765", pos(745, 620, 360, 18), { fontSize: 11, color: C.muted, alignment: "right" });
    addFooter(s, 4);
    setNotes(s, "This slide provides the environment evidence hub. The links use localhost HTTP paths rather than file URLs, so Google Slides can open them in the browser when the local server is running. Synthetic and DU each have three focused views; heiDATA has the source pair and geospatial benchmark.");
  }

  // Slide 5 — V1 method
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "04 / V1 baseline", "V1: the reproducible operating baseline", "Dynamic arrivals, queue-based dispatch, and bounded joint routing without online recourse.");
    addChip(s, "horizon", "120 min", pos(72, 180, 180, 84), C.navy, C.white);
    addChip(s, "phases", "3", pos(270, 180, 150, 84), C.orange, C.orangeLight);
    addChip(s, "queue", "dynamic", pos(438, 180, 170, 84), C.teal, C.tealLight);
    addChip(s, "recourse", "off", pos(626, 180, 150, 84), C.red, C.redLight);
    addRect(s, pos(72, 305, 505, 255), C.white, "rounded-2xl", C.line);
    addText(s, "V1 operating logic", pos(100, 330, 250, 24), { fontSize: 17, bold: true, color: C.navy2 });
    addBulletList(s, [
      "New tasks enter a waiting queue",
      "Each dispatch step evaluates feasible task/UAV pairings",
      "Joint routing checks payload, energy, return, and horizon",
      "A new event does not revise an active mission",
    ], pos(100, 370, 430, 145), 16, C.ink);
    addRect(s, pos(617, 305, 553, 255), C.navy, "rounded-2xl", C.navy);
    addText(s, "Phase weights", pos(650, 330, 180, 25), { fontSize: 17, bold: true, color: C.white });
    const phases = [["0–40", "HIGH", "3×", C.orange], ["40–80", "MEDIUM", "2×", "#A7F3D0"], ["80–120", "LOW", "1×", "#BFDBFE"]];
    phases.forEach(([time, label, weight, color], i) => {
      const y = 375 + i * 50;
      addText(s, time, pos(650, y, 100, 22), { fontSize: 17, bold: true, color });
      addText(s, label, pos(770, y, 130, 22), { fontSize: 16, color: C.white });
      addText(s, weight, pos(1030, y, 80, 22), { fontSize: 17, bold: true, color, alignment: "right" });
      if (i < 2) addLine(s, 650, y + 32, 430, "#36577B", 1);
    });
    addText(s, "V1 is the control condition for V2 and V2.1.", pos(650, 505, 430, 24), { fontSize: 14, color: "#CBD5E1" });
    addLinkList(s, [{ label: "Open V1 simulation replay", path: DEMO.v1 }], pos(650, 532, 430, 28), 14);
    addFooter(s, 5);
    setNotes(s, "V1 is the control condition. It runs for 120 minutes with high, medium, and low severity phases. Tasks arrive dynamically and wait in a queue, but an active route is not revised when a new task arrives. The linked replay shows one V1 mission evolving over time.");
  }

  // Slide 6 — V1 results
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "05 / V1 evidence", "V1 results: environment difficulty and fleet sensitivity", "A 240-run sweep shows lower DU service rates, workload pressure, and a dominant route-evaluation cost.");
    addRect(s, pos(70, 175, 650, 400), C.white, "rounded-2xl", C.line);
    addText(s, "Average served tasks by fleet size", pos(95, 195, 360, 22), { fontSize: 16, bold: true, color: C.navy2 });
    addChart(s, "line", {
      position: pos(92, 232, 600, 315),
      categories: ["3 UAV", "5 UAV", "8 UAV", "10 UAV"],
      series: [
        { name: "DU outdoor", values: [10.8, 17.1, 24.2, 28.3], line: { fill: C.orange, width: 3 }, fill: C.orange },
        { name: "Synthetic", values: [25.2, 36.3, 47.7, 52.4], line: { fill: C.blue, width: 3 }, fill: C.blue },
      ],
      hasLegend: true,
      legend: { position: "bottom", textStyle: { fontSize: 12, typeface: FONT } },
      lineOptions: { smooth: false, grouping: "standard" },
      xAxis: { textStyle: { fontSize: 11, typeface: FONT }, majorGridlines: { style: "solid", fill: C.white, width: 0 } },
      yAxis: { textStyle: { fontSize: 11, typeface: FONT }, majorGridlines: { style: "solid", fill: C.line, width: 1 }, numberFormatCode: "0" },
      dataLabels: { showValue: false },
    });
    addChip(s, "runs", "240", pos(755, 190, 170, 88), C.navy, C.white);
    addChip(s, "planner time in route eval", "≈96.6%", pos(945, 190, 225, 88), C.orange, C.orangeLight);
    addRect(s, pos(755, 300, 415, 275), C.white, "rounded-2xl", C.line);
    addText(s, "What the baseline tells us", pos(780, 325, 330, 24), { fontSize: 17, bold: true, color: C.navy2 });
    addBulletList(s, [
      "Task completion rate falls as load increases: DU 56.5% → 23.8%; Synthetic 87.3% → 57.3%",
      "DU outdoor is consistently more constrained by geometry and damage",
      "More UAVs increase service capacity, but route computation also grows",
      "Route evaluation consumes approximately 96.6% of planner time",
    ], pos(780, 365, 355, 160), 15, C.ink);
    addLinkList(s, [{ label: "Open V1 findings report (PDF)", path: DEMO.v1Report }], pos(780, 530, 350, 28), 14);
    addFooter(s, 6);
    setNotes(s, "The V1 matrix contains 240 runs: two environments, three task loads, four fleet sizes, and ten seeds. The curve shows the averaged fleet sensitivity. Under increasing load, task completion rate falls sharply, especially in DU outdoor. Route evaluation accounts for approximately 96.6 percent of planner time. The report link opens the full tables and detailed breakdowns.");
  }

  // Slide 7 — V2 method/demo
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "06 / V2 recourse", "V2: online recourse with feasibility protection", "A new task can replace one uncompleted task only when the revised mission remains feasible and improves J.");
    addRect(s, pos(70, 180, 600, 365), C.white, "rounded-2xl", C.line);
    addText(s, "One-for-one replacement", pos(100, 208, 310, 25), { fontSize: 18, bold: true, color: C.navy2 });
    addRect(s, pos(105, 285, 155, 92), C.blueLight, "rounded-xl", C.blueLight);
    addText(s, "ACTIVE\nROUTE", pos(105, 306, 155, 44), { fontSize: 22, bold: true, color: C.blue, alignment: "center" });
    addText(s, "→", pos(285, 310, 70, 40), { fontSize: 32, bold: true, color: C.orange, alignment: "center" });
    addRect(s, pos(380, 285, 155, 92), C.orangeLight, "rounded-xl", C.orangeLight);
    addText(s, "NEW TASK\nARRIVES", pos(380, 306, 155, 44), { fontSize: 21, bold: true, color: "#C2410C", alignment: "center" });
    addText(s, "ΔJ > 0 ?", pos(210, 405, 260, 38), { fontSize: 27, bold: true, color: C.teal, alignment: "center" });
    addBulletList(s, ["current onboard inventory", "payload / energy / return feasibility", "positive-gain guard only"], pos(110, 457, 460, 75), 15, C.slate);
    addRect(s, pos(710, 180, 460, 365), C.navy, "rounded-2xl", C.navy);
    addTag(s, "LIVE REPLAY", pos(745, 210, 112, 25), "#173E69", "#BFDBFE");
    addText(s, "One accepted replacement\ncan be replayed live", pos(745, 258, 365, 70), { fontSize: 27, bold: true, color: C.white });
    addText(s, "Seed 102  •  DU outdoor  •  30 tasks  •  3 UAVs", pos(747, 345, 370, 25), { fontSize: 15, color: "#CBD5E1" });
    addText(s, "Example: task_25 replaces task_20\non UAV_1; ΔJ ≈ +0.189", pos(747, 385, 350, 58), { fontSize: 18, color: "#A7F3D0" });
    addLinkList(s, [{ label: "Open dedicated V2 recourse replay", path: DEMO.v2 }], pos(745, 475, 370, 38));
    addFooter(s, 7);
    setNotes(s, "The dedicated V2 replay shows the first accepted replacement. Task_25 replaces task_20 on UAV_1 after checking the projected position, current onboard inventory, route feasibility, energy reserve, and return-to-base condition. The replacement is rejected whenever ΔJ is not positive.");
  }

  // Slide 8 — V2 results
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "07 / V2 evidence", "V2 results: objective gain with runtime overhead", "Recourse creates the largest gain in DU outdoor, while Synthetic shows a smaller but positive improvement.");
    addRect(s, pos(70, 178, 545, 355), C.white, "rounded-2xl", C.line);
    addText(s, "Objective: V1 vs V2", pos(95, 198, 260, 22), { fontSize: 16, bold: true, color: C.navy2 });
    addChart(s, "bar", {
      position: pos(90, 230, 505, 270),
      categories: ["DU outdoor", "Synthetic"],
      series: [
        { name: "V1", values: [10.43, 23.48], fill: C.slate },
        { name: "V2", values: [11.70, 23.84], fill: C.teal },
      ],
      hasLegend: true,
      legend: { position: "bottom", textStyle: { fontSize: 11, typeface: FONT } },
      barOptions: { direction: "column", grouping: "clustered", gapWidth: 55 },
      xAxis: { textStyle: { fontSize: 11, typeface: FONT } },
      yAxis: { textStyle: { fontSize: 11, typeface: FONT }, majorGridlines: { style: "solid", fill: C.line, width: 1 }, numberFormatCode: "0.0" },
      dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 10, typeface: FONT } },
    });
    addRect(s, pos(645, 178, 525, 355), C.white, "rounded-2xl", C.line);
    addText(s, "Runtime: V1 vs V2 (sec)", pos(670, 198, 280, 22), { fontSize: 16, bold: true, color: C.navy2 });
    addChart(s, "bar", {
      position: pos(665, 230, 480, 270),
      categories: ["DU outdoor", "Synthetic"],
      series: [
        { name: "V1", values: [20.2, 3.7], fill: C.slate },
        { name: "V2", values: [59.4, 10.4], fill: C.orange },
      ],
      hasLegend: true,
      legend: { position: "bottom", textStyle: { fontSize: 11, typeface: FONT } },
      barOptions: { direction: "column", grouping: "clustered", gapWidth: 55 },
      xAxis: { textStyle: { fontSize: 11, typeface: FONT } },
      yAxis: { textStyle: { fontSize: 11, typeface: FONT }, majorGridlines: { style: "solid", fill: C.line, width: 1 }, numberFormatCode: "0" },
      dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 10, typeface: FONT } },
    });
    addChip(s, "DU objective gain", "+12.2%", pos(90, 565, 220, 70), C.teal, C.tealLight);
    addChip(s, "Synthetic gain", "+1.5%", pos(330, 565, 200, 70), C.blue, C.blueLight);
    addChip(s, "trade-off", "runtime ↑", pos(550, 565, 210, 70), C.orange, C.orangeLight);
    addText(s, "Mean delay falls from 31.6 to 23.2 min in DU and from 18.3 to 16.1 min in Synthetic. Served-task count changes only slightly.", pos(790, 575, 350, 46), { fontSize: 13, bold: true, color: C.slate });
    addLinkList(s, [{ label: "Open V2 comparative report (PDF)", path: DEMO.v2Report }], pos(790, 630, 350, 25), 14);
    addFooter(s, 8);
    setNotes(s, "The paired V2 comparison has three takeaways. DU objective increases by approximately 12.2 percent and Synthetic by approximately 1.5 percent. Mean delay decreases in both environments, while runtime increases because recourse repeatedly checks candidate route feasibility. The report link contains the full objective, delay, runtime, and rejection matrices.");
  }

  // Slide 9 — V2.1 cache setup
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "08 / V2.1 cache-aware planning", "V2.1: testing one-slot reserve capacity", "One reserve parcel is loaded at dispatch time and evaluated under uniform and water-heavy cache policies.");
    addRect(s, pos(70, 185, 490, 350), C.white, "rounded-2xl", C.line);
    addText(s, "Mechanism", pos(100, 213, 180, 24), { fontSize: 18, bold: true, color: C.navy2 });
    const steps = [["01", "ordinary V2 route", C.blue], ["02", "one reserve parcel", C.orange], ["03", "future task arrives", C.teal], ["04", "guards + ΔJ > 0", C.green]];
    steps.forEach(([n, label, color], i) => {
      const y = 260 + i * 59;
      addRect(s, pos(105, y, 48, 34), color, "rounded-lg", color);
      addText(s, n, pos(105, y + 4, 48, 25), { fontSize: 13, bold: true, color: C.white, alignment: "center" });
      addText(s, label, pos(180, y + 3, 285, 26), { fontSize: 18, color: C.ink });
      if (i < 3) addLine(s, 128, y + 34, 2, C.line, 25);
    });
    addRect(s, pos(600, 185, 570, 350), C.navy, "rounded-2xl", C.navy);
    addText(s, "Policies under test", pos(630, 215, 260, 24), { fontSize: 18, bold: true, color: C.white });
    addTag(s, "UNIFORM", pos(630, 270, 105, 26), "#173E69", "#BFDBFE");
    addText(s, "reserve content sampled uniformly", pos(755, 270, 330, 24), { fontSize: 16, color: C.white });
    addTag(s, "WATER-HEAVY", pos(630, 325, 125, 26), "#134E4A", "#A7F3D0");
    addText(s, "more likely to cache water payload", pos(775, 325, 310, 24), { fontSize: 16, color: C.white });
    addLine(s, 630, 385, 450, "#36577B", 1);
    addText(s, "Guard conditions", pos(630, 405, 180, 22), { fontSize: 15, bold: true, color: "#CBD5E1" });
    addText(s, "payload • mass • energy • return • horizon", pos(630, 438, 460, 25), { fontSize: 17, color: C.white });
    addChip(s, "paired scenarios", "240", pos(80, 575, 190, 70), C.navy, C.white);
    addChip(s, "metric rows", "720", pos(285, 575, 190, 70), C.teal, C.tealLight);
    addChip(s, "trace families", "240", pos(490, 575, 190, 70), C.orange, C.orangeLight);
    addText(s, "Question: does the service-value gain justify the cache overhead?", pos(760, 588, 360, 30), { fontSize: 18, bold: true, color: C.navy2, alignment: "center" });
    addFooter(s, 9);
    setNotes(s, "V2.1 adds one reserve parcel to the ordinary V2 route. The cache is loaded at dispatch time and checked against payload, mass, energy, return, and horizon constraints. The experiment compares uniform sampling with a water-heavy prior. Subsequent replacement decisions still use the positive ΔJ rule.");
  }

  // Slide 10 — V2.1 results
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "09 / V2.1 evidence", "V2.1 results: modest gain and low cache hit rate", "The water-heavy policy performs slightly better, but most reserve payload returns unused.");
    addRect(s, pos(70, 178, 520, 335), C.white, "rounded-2xl", C.line);
    addText(s, "Gain vs V2 control", pos(95, 198, 250, 22), { fontSize: 16, bold: true, color: C.navy2 });
    addChart(s, "bar", {
      position: pos(92, 230, 480, 245),
      categories: ["Uniform", "Water-heavy"],
      series: [
        { name: "Δ objective", values: [0.238, 0.328], fill: C.teal },
        { name: "Δ served", values: [0.288, 0.454], fill: C.orange },
      ],
      hasLegend: true,
      legend: { position: "bottom", textStyle: { fontSize: 10, typeface: FONT } },
      barOptions: { direction: "column", grouping: "clustered", gapWidth: 55 },
      xAxis: { textStyle: { fontSize: 10, typeface: FONT } },
      yAxis: { textStyle: { fontSize: 10, typeface: FONT }, majorGridlines: { style: "solid", fill: C.line, width: 1 }, numberFormatCode: "0.0" },
      dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 9, typeface: FONT } },
    });
    addRect(s, pos(620, 178, 550, 335), C.white, "rounded-2xl", C.line);
    addText(s, "Cache activity", pos(645, 198, 220, 22), { fontSize: 16, bold: true, color: C.navy2 });
    addChart(s, "bar", {
      position: pos(640, 230, 505, 245),
      categories: ["Uniform", "Water-heavy"],
      series: [
        { name: "Used / scenario (%)", values: [14.3, 14.8], fill: C.teal },
        { name: "Returned / scenario (%)", values: [111.9, 110.0], fill: C.slate },
      ],
      hasLegend: true,
      legend: { position: "bottom", textStyle: { fontSize: 10, typeface: FONT } },
      barOptions: { direction: "column", grouping: "clustered", gapWidth: 55 },
      xAxis: { textStyle: { fontSize: 10, typeface: FONT } },
      yAxis: { textStyle: { fontSize: 10, typeface: FONT }, majorGridlines: { style: "solid", fill: C.line, width: 1 }, numberFormatCode: "0" },
      dataLabels: { showValue: false },
    });
    addChip(s, "best policy", "water-heavy", pos(90, 545, 225, 70), C.teal, C.tealLight);
    addChip(s, "hit rate", "≈14–15%", pos(335, 545, 190, 70), C.orange, C.orangeLight);
    addChip(s, "decision", "1 slot; defer 2nd", pos(545, 545, 235, 70), C.navy, C.white);
    addText(s, "Uniform: +0.238 objective and +0.288 served. Water-heavy: +0.328 objective and +0.454 served. Cache remains useful, but it is not yet a dominant policy lever.", pos(810, 555, 330, 58), { fontSize: 13, bold: true, color: C.slate, alignment: "center" });
    addLinkList(s, [{ label: "Open V2.1 cache-aware report (PDF)", path: DEMO.v21Report }], pos(810, 628, 330, 25), 14);
    addFooter(s, 10);
    setNotes(s, "The V2.1 gain is positive but modest. Uniform improves objective by 0.238 and served tasks by 0.288; water-heavy improves them by 0.328 and 0.454. Hit rate remains around 14 to 15 percent, and most reserve payload returns unused. The evidence supports retaining one slot while deferring a second slot or adaptive prior.");
  }

  // Slide 11 — overall status/next steps
  {
    const s = deck.slides.add();
    s.background.fill = C.pale;
    addTitle(s, "10 / Status and next steps", "Overall status: evidence is complete; calibration and scale remain", "The remaining decisions concern model calibration, planner scalability, and final thesis integration.");
    addRect(s, pos(70, 180, 520, 365), C.greenLight, "rounded-2xl", C.greenLight);
    addText(s, "COMPLETED", pos(100, 210, 200, 22), { fontSize: 15, bold: true, color: C.green });
    addBulletList(s, [
      "V1 baseline + 240-run evidence sweep",
      "Synthetic / DU / heiDATA environment artifacts",
      "V2 recourse implementation + replayable demo",
      "V2.1 cache-aware comparison + reports",
      "Trace, metrics, and HTML visualization evidence",
    ], pos(100, 252, 430, 205), 17, C.ink);
    addRect(s, pos(630, 180, 540, 365), C.white, "rounded-2xl", C.line);
    addText(s, "NEXT / LIMITATIONS", pos(660, 210, 260, 22), { fontSize: 15, bold: true, color: C.orange });
    addBulletList(s, [
      "Calibrate energy coefficients with field data",
      "Expand sensitivity analysis for synthetic task and damage assumptions",
      "Reduce V2 runtime through candidate pruning",
      "Clarify the boundary between the heuristic and a scalable planner",
      "Final thesis integration: one canonical formulation",
    ], pos(660, 252, 455, 205), 17, C.ink);
    addRect(s, pos(120, 575, 1040, 48), C.navy, "rounded-xl", C.navy);
    addText(s, "Takeaway: V1 explains the baseline; V2 adds responsiveness; V2.1 tests reserve capacity.", pos(150, 586, 980, 25), { fontSize: 19, bold: true, color: C.white, alignment: "center" });
    addText(s, "Detailed result tables and full traces remain available through the linked reports.", pos(270, 650, 740, 20), { fontSize: 13, color: C.muted, alignment: "center" });
    addFooter(s, 11);
    setNotes(s, "The evidence package is complete for V1, V2, and V2.1. The next work is to calibrate energy, broaden sensitivity analysis, reduce recourse runtime, clarify the scalable planner boundary, and integrate one canonical formulation into the thesis.");
  }

  await fs.mkdir(PREVIEWS, { recursive: true });
  for (const [index, slide] of deck.slides.items.entries()) {
    const png = await deck.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(PREVIEWS, `slide-${String(index + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
  }
  const montage = await deck.export({ format: "webp", montage: true });
  await fs.writeFile(path.join(BUILD, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));
  const candidate = path.join(BUILD, "candidate.pptx");
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(candidate);
  console.log(JSON.stringify({ candidate, previews: PREVIEWS, slideCount: deck.slides.items.length }));
}

build().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
