# MASTER PROMPT: Analyse the whole SiteGuard AI project and build an extraordinary 10-slide presentation

You are running inside the **SiteGuard AI** project folder. Act as three experts at once:

1. **A senior software and ML analyst.** Read and understand the entire project.
2. **A world-class presentation designer.** Create a stunning, premium, cinematic deck.
3. **A presentation coach.** Write simple speaker notes and a script that make the presenter confident.

**Presenter:** JUNAID AHMAD · Reg. No. 12419395
**Event:** class presentation to the teacher, about 10 minutes plus a short live demo (the presenter uploads a construction photo in the app). Date: 26 November 2026.

The deck must be **at most 10 slides**, easy to explain, visually extraordinary, and **strictly truthful**. Complete every phase below in order. Do not skip the reading phase.

---

## PHASE 1: Read and understand the whole project

### 1.1 Make an inventory first

List the full folder tree, excluding the paths in 1.3. Write it to `presentation/analysis/PROJECT_MAP.md`, with one line per folder saying what it contains.

### 1.2 Then read everything in this order

Open and read every text file in these locations. Do not stop at the first few files.

| Order | What to read | What to learn |
|---|---|---|
| 1 | `README.md`, `requirements.txt`, `pytest.ini` | Purpose, how to run, dependencies |
| 2 | The three root specifications: `SiteGuard_AI_Master_Engineering_Specification.md`, `SiteGuard_AI_Frontend_Completion_Master_Specification.md`, `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` | Original goals and rules |
| 3 | Everything under `docs/`: `ARCHITECTURE.md`, `DATASET.md`, `ANNOTATION_POLICY.md`, `TRAINING.md`, `EVALUATION.md`, `IMPLEMENTATION_LOG.md`, `docs/reports/`, `docs/frontend_redesign/` | Design, data, training and evaluation method, history |
| 4 | `configs/` (all `.yaml`) | Classes, model registry, thresholds (read-only) |
| 5 | `app.py` | The 8 pages and every user workflow |
| 6 | All Python files under `src/`: `detection/`, `compliance/`, `events/`, `evaluation/`, `training/`, `utils/`, `ui/` | How detection, rule checking, events, evaluation and the dashboard work |
| 7 | `scripts/` | Training, evaluation and helper scripts |
| 8 | `tests/`; then run `.venv/bin/python -m pytest --collect-only -q` | What is tested, and the test count (collection only; do not run the suite) |
| 9 | Result files: `experiments/evaluation/**/metrics.json`, `experiments/viewpoint_results/*.json`, `models/trained/*.json`, `models/trained/**/model_card.json`, and every `*.json`, `*.csv` and `*.md` under `experiments/accuracy_improvement/`, including `reports/REPORT-018` to `REPORT-025` | Real measured numbers and the research decision |
| 10 | Every report under `experiments/**/reports/` (accuracy improvement, camera quality audit, frontend completion, frontend redesign, including `FRONTEND-REDESIGN-FINAL-HANDOFF.md` and `FRONTEND-REDESIGN-REPORT-008-REFERENCE-MATCH.md`) | Engineering work: camera fixes, UI redesign, testing, limitations |

### 1.3 Do not open these (privacy, binary or irrelevant)

| Path | Reason |
|---|---|
| `outputs/evidence/` | **Private:** real webcam evidence frames showing the presenter |
| `outputs/videos/` | Private videos |
| `experiments/live_audit/webcam/` | **Private** webcam recordings |
| any `*.db`, `*.sqlite` | Live event database with personal session data |
| `models/**/*.pt`, `*.onnx`, `*.engine` | Binary model weights |
| `data/` image folders and `../construction-ppe/` images | Thousands of dataset images; read only the `.yaml` and `.md` files there |
| `outputs/logs/`, `experiments/**/logs/` | Large raw logs, no extra information |
| `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ultralytics/`, `node_modules/` | Environment and caches |

### 1.4 Write the analysis

Create `presentation/analysis/PROJECT_ANALYSIS.md` (about 2 pages). Cover:
- **Problem and goal.**
- **Architecture:** components and data flow.
- **Dataset:** source, licence, size, classes.
- **Model and training:** settings, hardware, time.
- **Evaluation:** every metric with its split and size.
- **The bigger-model experiment** and its decision.
- **The live camera pipeline** and its engineering fixes.
- **The 8 app pages.**
- **Testing.**
- **Limitations and future work.**

Every number must name its source file.

---

## PHASE 2: Verify the facts

### 2.1 Fact table

Create `presentation/FACTS.md`: one table row per number used anywhere in the deck, with columns value, meaning, data split and size, and source file.

### 2.2 Cross-check

Cross-check against the **verified fact sheet** below, which was taken from the project files on 25 Nov 2026.
- If a file disagrees, use the file value and record the difference in your final summary.
- Never invent, round up or "improve" a number.

### Verified fact sheet

**Project**
- **SiteGuard AI:** an academic computer-vision prototype for construction-site PPE (personal protective equipment) monitoring.
- **Use:** decision support only. Detections are *potential* issues for human review.
- **Privacy:** runs fully on one laptop (MacBook Air M5, Apple GPU via PyTorch MPS). No image, video or camera frame leaves the computer.
- **Interface:** Streamlit dashboard on `localhost`, with 8 pages: Overview, Live Monitoring, Image Inspection, Video Inspection, Safety Events, Analytics, Model Evaluation, Settings / About.
- **Inputs:** uploaded images, uploaded videos, live browser webcam (WebRTC).
- **Tests:** 205 automated tests passing.

**Dataset**
- **Source:** Ultralytics Construction-PPE (licence CC BY 4.0).
- **Size:** 1,000 labelled images, split 800 training / 200 validation. The validation set has 2,961 labelled objects.
- **12 classes:**
  - PPE present: helmet, vest, gloves, boots, goggles.
  - PPE missing: no_helmet, no_vest, no_gloves, no_boots, no_goggle.
  - Other: Person, forklift.
- **Required PPE in the app:** helmet, vest, gloves.

**Active model and training**
- **Model:** YOLO26n (nano), fine-tuned.
- **Training:** 640 px input, 30 epochs, batch 8, 1,273 s (about 21 min) on the MacBook Air M5 GPU (MPS).
- **Software:** Ultralytics 8.4.215, PyTorch 2.15.0, Python 3.12.

**Accuracy (validation set: 200 images, 640 px, Ultralytics val; precision and recall at the best-F1 confidence)**

| Metric | Value | Plain meaning |
|---|---|---|
| Precision | 0.832 | Detections are right about 83 % of the time |
| Recall | 0.681 | Finds about 68 % of the labelled objects |
| mAP50 | 0.734 | Overall box quality at 50 % overlap |
| mAP50-95 | 0.523 | Same, averaged over stricter overlaps |

- **Per-class mAP50:**
  - Person 0.940, goggles 0.924, vest 0.887, helmet 0.825, forklift 0.807, gloves 0.793;
  - boots 0.771, no_boots 0.748, no_vest 0.692, no_helmet 0.652, no_gloves 0.620, no_goggle 0.148.
- **At the app's operating confidence of 0.25** (same set): precision 0.884, recall 0.745.

**Speed** (recorded webcam replay, 149 frames at about 30 fps, MacBook Air M5; not a physical-camera test)
- **YOLO26n:** 29.8 frames analysed per second, 0 dropped, inference 20.3 ms mean / 24.8 ms p95.
- **E3 (YOLO26m, 896 px):** 23.7 fps, 31 of 149 dropped, 42.0 ms mean.

**Bigger-model experiment (E3 = YOLO26m at 896 px)**
- **Same validation set:**
  - mAP50: 0.854 (E3) vs 0.734 (YOLO26n).
  - mAP50-95: 0.628 vs 0.523.
  - Recall at 0.25: 0.858 vs 0.745.
  - These are optimistic, because this set also selected the training checkpoints.
- **Held-back (locked) test, 160 images, 2,480 objects, run once:**
  - mAP50 0.847, against a target of 0.93 that was **not met**;
  - mAP50-95 0.644;
  - precision 0.885 (95 % interval 0.863–0.906);
  - recall 0.862 (95 % interval 0.832–0.890).
- **Decision:** E3 **not promoted**; YOLO26n stays active (accuracy gate missed, too slow for live use).

**Rules (read-only)**
- **Detection:** confidence ≥ 0.25; NMS IoU 0.5.
- **Worker:** a Person box with confidence ≥ 0.4.
- **Statuses:**
  - potential violation: missing-PPE box ≥ 0.5;
  - compliant evidence: PPE ≥ 0.4;
  - uncertain: never counted as compliant.
- **Live and video events:** the problem must persist 3 analysed frames; repeats are suppressed for 30 s.
- **Review:** a person sets each event to pending, confirmed, false positive or dismissed. Events can be exported as CSV.

**Honest limitations**
- **Missing PPE:** recall is below 0.90 for every class.
  - YOLO26n at 0.25: no_helmet 0.615, no_gloves 0.567, no_goggle 0.171, no_boots 0.674, no_vest 0.623.
- **Real-site gap** (held-back test, E3): real-site photos mAP50 0.592 (47 images) vs close-ups 0.951 (113 images).
- **Viewpoint** (frontal-only model): mAP50-95 0.639 frontal vs 0.185 overhead.
- **Labels:** 178 possibly wrong labels not yet reviewed.
- **Camera:** physical-camera validation is listed as pending. Real-time figures come from a recorded replay.
- **Status:** a prototype on one public dataset; not a certified safety system.

---

## PHASE 3: Design an extraordinary deck

### 3.1 Creative direction

**Mood:** "cinematic industrial night shift". Premium, calm, confident, and like the app's own dashboard: deep navy, graphite and black surfaces with warm gold and amber light, and a construction site at dusk.

- **Think:** a high-end product keynote, not a school template.
- **Look:** generous space, big numbers, few words, precise alignment, subtle gold light.
- **Avoid:** no neon, clip-art, stock photos, emoji, rainbow charts, walls of text or default PowerPoint styles.

### 3.2 Design system (follow exactly)

**Canvas and grid**
- 16:9, 13.333 × 7.5 in.
- Margins: 0.6 in left/right, 0.5 in top, 0.45 in bottom.
- 12-column grid, 0.25 in gutters.

**Colours**

| Token | Hex | Use |
|---|---|---|
| Background ink | `#0B1119` | Every slide |
| Navy | `#0F1824` | Side bands |
| Graphite panel | `#161D27` | Cards and panels, about 90 % opaque |
| Gold | `#D6A24D` | Rules, chart series, kicker text, 1 pt panel edges at 35 % opacity |
| Amber | `#E49A32` | Highlights, key numbers |
| Ivory | `#F3F0E8` | Main text |
| Muted | `#AEB6BF` | Secondary text |
| Metadata | `#8D98A5` | Footers, sources |
| OK / Warn / Critical / Info | `#3FA66B` / `#E0A030` / `#E5484D` / `#5B8DEF` | Status only, always with a word next to them |

**Icon-tile gradients:**
- orange `#FFB547` → `#C9650F`
- green `#5BD07F` → `#1C7A3C`
- red `#F2606A` → `#A1202B`
- blue `#5FA2FF` → `#1F57C3`

**Typography**
- **Headings, numbers, labels:** **Avenir Next Condensed** Bold or Demi Bold. Fallbacks: Arial Narrow Bold, then Arial.
  - Headline 30–32 pt.
  - Title-slide name 54–60 pt.
  - KPI numbers 44–54 pt.
  - Kicker 12 pt, gold, uppercase, letter-spaced 1.5 pt.
- **Body:** Avenir Next Regular (fallback Calibri), 16–20 pt; captions 11 pt.

**Signature elements (use them consistently)**
- **Header zone:** kicker, headline that states the takeaway, then a 1.25 pt gold rule 3 grid columns wide.
- **Progress dots:** 10 small dots bottom-centre; the current slide's dot is amber, the others `#283240`.
- **Footer:**
  - left: "SiteGuard AI · Junaid Ahmad · 12419395", 10 pt metadata colour;
  - right: "03 / 10".
  - Not on the title slide.
- **Panels:** rounded rectangles (corner about 0.12 in), graphite fill at about 90 % opacity, 1 pt gold edge at 35 %, soft shadow.
- **Slanted KPI card:**
  - Shape: a freeform parallelogram, left edge straight, right edge slanting 0.35 in inward at the bottom.
  - Fill: graphite gradient `#2E3644` → `#0C1119`.
  - Outline: 0.75 pt gold at 70 % opacity.
  - Inside: a 0.62 in rounded icon tile (gradient), label (14 pt ivory) and value (48 pt Avenir Next Condensed Bold).
- **Scene band** (title and closing slides): the original image `assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png`.
  - Place it on the right 45 % (on the left for the closing slide).
  - Crop it to keep the crane, the building and the worker with the tablet.
  - Add a dark gradient overlay towards the text side.
  - Draw two thin angular gold lines (1.25 pt and 0.75 pt at 40 %) along its edge.
- **Device frame:** on the demo slide, draw a simple laptop outline (rounded dark rectangle with a thin gold edge, plus a base trapezoid) and place the app screenshot inside it as the screen.
- **Icons:** draw them with shapes only.
  - Person: oval + rounded rectangle.
  - Shield: pentagon or chevron.
  - Warning: triangle + "!".
  - Camera: rounded rectangle + triangle.
  - Database: stacked ovals.
  - Chip: square inside a square.
  - Check: ✓.
- **Charts:** native, editable bar charts only.
  - Gold series; missing-PPE classes highlighted in amber; second series slate `#7C8B9C`.
  - Transparent background; gridlines `#283240` 0.5 pt; ivory data labels with 3 decimals.
  - mAP, precision and recall axes run from 0 to 1.
  - A 10 pt source line under each chart.

### 3.3 Layout templates

```
A. TITLE                                   B. CONTENT + VISUAL
+--------------------------+-------------+ +------------------------------------------+
| KICKER (gold)            |             | | KICKER                                   |
| SiteGuard AI (60pt)      |  SCENE BAND | | Takeaway headline                        |
| subtitle (22pt)          |  photo +    | | ---- gold rule                           |
| ---- gold rule           |  gold lines | | +---------------+ +--------------------+ |
| JUNAID AHMAD             |  + slogan   | | | 3-5 short     | | chart / diagram /  | |
| Reg. No. 12419395        |             | | | bullets       | | screenshot panel   | |
| 471 Project · date       |             | | +---------------+ +--------------------+ |
+--------------------------+-------------+ | footer        o o o O o o o o o o   03/10 |
                                           +------------------------------------------+
C. KPI DASHBOARD                           D. PIPELINE
+------------------------------------------+ +------------------------------------------+
| [/ KPI /] [/ KPI /] [/ KPI /] [/ KPI /]  | | (1)--->(2)--->(3)--->(4)--->(5)          |
| +--------------------------------------+ | | icon tile + step + one line each         |
| | native bar chart                     | | | banner: runs locally, nothing uploaded   |
| +--------------------------------------+ | +------------------------------------------+
+------------------------------------------+
E. VERSUS                                  F. DEMO (laptop frame)
+-------------------+  VS  +---------------+ +------------------------------------------+
| YOLO26n (active)  |      | E3 (research) | |  +----------- laptop -----------+  call- |
| big numbers       |      | big numbers   | |  |  app screenshot as screen    |  outs  |
+-------------------+------+---------------+ |  +------------------------------+        |
| DECISION banner (amber)                  | |  two small screenshot panels below       |
+------------------------------------------+ +------------------------------------------+
```

---

## PHASE 4: Build the 10 slides

**Text rules:**
- At most 5 bullets per slide and at most 12 words per bullet.
- Every headline states the takeaway.

**Speaker notes:**
- 80–120 words of simple English on every slide.
- Explain every technical term the first time it is used.
- End with **"If asked:"** and a one-line answer.

### Slide 1: Title (template A)
- **Kicker:** CONSTRUCTION-SITE SAFETY · COMPUTER VISION
- **Title:** SiteGuard AI
- **Subtitle:** AI-assisted PPE monitoring that runs on one laptop
- **Presenter block:**
  - JUNAID AHMAD (bold, 22 pt)
  - Reg. No. 12419395
  - 471 Project · 26 November 2026
- **Scene band** with the slogan "Safer Sites." in gold and "Smarter Tomorrow." in ivory.
- **Notes:** greet the teacher, give your name, and say the idea in one sentence.

### Slide 2: The problem and the goal (template B)
- **Headline:** Missing PPE is common, and supervisors cannot watch everything
- **Three panels:**
  - Problem: helmets, vests and gloves get missed; manual checks miss moments.
  - Idea: a camera model spots potential missing PPE.
  - Principle: the AI suggests, a person decides.
- **Checklist:**
  - ✓ detects workers + 12 object types;
  - ✓ checks helmet, vest, gloves per worker;
  - ✓ records evidence;
  - ✓ human review + CSV report;
  - ✓ fully local.

### Slide 3: How it works (template D)
- **Headline:** From camera frame to reviewed safety event in five steps
- **Steps:**
  1. Input: image, video, live webcam.
  2. Detect: YOLO26n finds people, PPE, missing PPE.
  3. Check rules: link each item to the right worker.
  4. Confirm: 3 analysed frames; 30-s repeat filter.
  5. Review: dashboard, evidence, human decision, CSV.
- **Banner:** "Runs locally on a MacBook Air M5 · no image leaves the computer".

### Slide 4: The data (template B with chips)
- **Headline:** 1,000 labelled construction images, 12 object classes
- **Facts:** Ultralytics Construction-PPE, CC BY 4.0 · 800 training / 200 validation · 2,961 objects in validation.
- **Chips:** PPE present (gold), PPE missing (amber), Other (slate).
- **Small native bar chart:** 800 vs 200.

### Slide 5: Model and training (template C variant)
- **Headline:** A small, fast model trained in 21 minutes on a laptop
- **KPI cards:** YOLO26n (nano) · 30 epochs / 21 min · 640 px input · 29.8 fps live, 0 dropped
- **Panel:** "Why nano? About 20 ms per frame keeps live video at 30 fps (recorded replay, 149 frames)."

### Slide 6: Accuracy (template C)
- **Headline:** Strong on people and PPE, weaker on missing goggles
- **KPI cards:** Precision 0.832 · Recall 0.681 · mAP50 0.734 · mAP50-95 0.523
  - Caption: "Validation set, 200 images, 640 px".
- **Chart:** native horizontal bar chart of the 12 per-class mAP50 values, sorted, with missing-PPE classes in amber.
- **Mini legend:**
  - precision = how often a detection is right;
  - recall = how much it finds;
  - mAP50 = box quality at 50 % overlap.

### Slide 7: The bigger-model experiment (template E)
- **Headline:** A bigger model was more accurate, but not accurate or fast enough
- **Left, YOLO26n:** 0.734 mAP50 · 29.8 fps · 0 dropped · 20 ms
- **Right, E3 (YOLO26m 896 px):** 0.854 validation / 0.847 locked test (target 0.93) · 23.7 fps · 31 dropped · 42 ms
- **Chart:** grouped bar chart of mAP50 and recall at 0.25 on the same validation set.
- **Decision banner:** "E3 not promoted. YOLO26n stays active for real-time use."

### Slide 8: The application and live demo (template F)
- **Headline:** An 8-page dashboard, and now a live demo
- **Laptop frame:** `experiments/frontend_redesign/evidence/reference_match/01_overview_1920x1080_redacted.png`
- **Small panels:**
  - `experiments/frontend_redesign/evidence/phase4_all_pages/full/full_image_inspection_result_1440.png`, cropped to the image pair and result;
  - `experiments/frontend_redesign/evidence/reference_match/05_safety_events_1470x830_redacted.png`.
- **Callouts:**
  - upload a photo, see boxes + per-worker status;
  - a person reviews every event;
  - live webcam about 30 fps;
  - everything stays on this laptop.
- **Bottom cue (amber):** "Live demo: upload a site photo in Image Inspection"
- **Notes:** list the exact clicks.
  1. Image Inspection.
  2. Upload.
  3. Show the annotated image and the compliance tab.
  4. Safety Events.

### Slide 9: Honest limitations (template B)
- **Headline:** What the model cannot do yet
- **Bullets** (each with an icon *and* text):
  - Missing-PPE recall below 0.90 for every class.
  - Real-site photos 0.592 vs close-ups 0.951 mAP50.
  - Overhead views 0.185 vs frontal 0.639 (mAP50-95).
  - 178 possibly wrong labels to review.
  - Prototype, not a certified safety system.
- **Optional mini bar chart:** 0.592 vs 0.951.

### Slide 10: Conclusion (template A mirrored, scene band on the left)
- **Headline:** SiteGuard AI works today, and the path to better is clear
- **Delivered ✓:**
  - local real-time system (29.8 fps);
  - 8-page dashboard with human review;
  - honest evaluation;
  - 205 automated tests.
- **Next →:**
  - more real-site and overhead data;
  - label review;
  - faster large model;
  - multi-camera sites.
- **Closing line:** "Thank you · Questions?" followed by "JUNAID AHMAD · 12419395".

---

## PHASE 5: Hard rules (apply throughout)

1. **At most 10 slides.** No appendix.
2. **Real numbers only,** each listed in `FACTS.md` with its source. Every metric states its split and size.
3. **Never use the mock values of the design reference image** `experiments/frontend_redesign/reference/approved_reference_2047x331.png`: 94.2 % compliance, "Active", "03", "1920 × 1080 · 30 FPS", "69 %", "Zone B". Use that image for mood only; never place it in the deck.
4. **Wording:**
   - Use "potential violation", "detector confidence" and "decision support".
   - Never use "production-ready", "certified", "guarantees safety", "93–95 % accuracy" or "compliance rate".
5. **Images:** use only those named in this prompt. Nothing from the private paths in 1.3.
6. **No project changes.**
   - Do not edit, move or delete any existing project file.
   - Do not install anything into the project `.venv`. Create `presentation/.venv` and install `python-pptx` there.
   - Write only inside `presentation/`.
7. **No downloaded assets:** no stock photos, web fonts or icon packs.
8. **No other personal data:** add none beyond the presenter's name and Reg. No. given here.

---

## PHASE 6: Build and export

1. **Write `presentation/build_deck.py`** (python-pptx) and run it to create `presentation/SiteGuard_AI_Presentation.pptx`.
   - **Transparency:** append `<a:alpha val="90000"/>` to the shape's `a:srgbClr` using `lxml`.
   - **Gradients:** `fill.gradient()`.
   - **Slanted cards:** `shapes.build_freeform(...)`.
   - **Charts:** `CategoryChartData` + `add_chart`, styling each series and point.
   - **Notes:** `notes_slide.notes_text_frame`.
   - **Images:** keep the aspect ratio; crop only with the `crop_*` properties.
   - **Fonts:** set `font.name` on every run.
2. **Export a PDF** if LibreOffice exists: `soffice --headless --convert-to pdf --outdir presentation presentation/SiteGuard_AI_Presentation.pptx`.
3. **Make previews** if `pdftoppm` exists: `pdftoppm -png -r 80 presentation/SiteGuard_AI_Presentation.pdf presentation/previews/slide`. Look at every preview and fix overflow, overlap, misalignment and low contrast.
4. **Write `presentation/SPEAKER_SCRIPT.md`:** the full 10-minute script, slide by slide, in simple English, with timings that add up to about 10 minutes plus 2 minutes of demo.
5. **Write `presentation/QA_CHEATSHEET.md`:** the 12 most likely teacher questions, each with a 2–3 sentence answer based only on the project files. Include:
   - What is mAP?
   - Why YOLO26n and not a bigger model?
   - How do you avoid false alarms?
   - Is it safe to rely on?
   - What data did you use?
   - What would you improve?
   - How does the live camera work?
   - Where is the data stored?

---

## PHASE 7: Final quality check (all must pass)

- [ ] 10 slides or fewer. Every slide has speaker notes with an "If asked:" line.
- [ ] Name "JUNAID AHMAD" and "Reg. No. 12419395" are spelled exactly, on the title and closing slides and in the footer.
- [ ] Every number appears in `FACTS.md` with its source; at least 10 spot-checked against the files.
- [ ] No mock values, forbidden phrases or private files.
- [ ] No text overflow or overlapping shapes, and consistent margins, fonts, header, footer and progress dots.
- [ ] Text contrast is high (ivory or muted on dark); status is never shown by colour alone.
- [ ] The project is untouched; only `presentation/` was created.

**Final reply, short:**
- list the files created;
- list any number that differed from the fact sheet, and which value you used;
- list anything you could not do (for example no PDF without LibreOffice).
