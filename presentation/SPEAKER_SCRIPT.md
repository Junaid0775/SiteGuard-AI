# SiteGuard AI — speaker script

**Presenter:** JUNAID AHMAD · Reg. No. 12419395
**Event:** 471 Project · 26 November 2026 · about 10 minutes, plus a live demo
**Deck:** `SiteGuard_AI_Presentation.pptx` (10 slides)

How to use this: each block is what you say, in simple English, with a time budget.
The words in **bold** are the ones to stress. Everything is safe to say aloud: every
number is in `FACTS.md` with its source.

Running order at a glance:

| # | Slide | Time | Cumulative |
|---|---|---|---|
| 1 | Title | 0:40 | 0:40 |
| 2 | Problem and goal | 1:00 | 1:40 |
| 3 | How it works | 1:05 | 2:45 |
| 4 | The data | 0:55 | 3:40 |
| 5 | Model and training | 0:55 | 4:35 |
| 6 | Accuracy | 1:10 | 5:45 |
| 7 | The bigger-model experiment | 1:10 | 6:55 |
| 8 | The app + **live demo** | 2:20 | 9:15 |
| 9 | Limitations | 0:55 | 10:10 |
| 10 | Conclusion | 0:35 | 10:45 |

That is 10:45 with the demo included. If the clock is tight, cut the demo to 90 seconds
(skip the Safety Events step) and take 15 seconds off slides 3 and 7. If you are early,
add the optional lines marked *[if time]*.

---

## Before you start (not timed)

1. Laptop open on the desktop, deck already open in presentation mode on slide 1.
2. Dashboard already running in a browser tab: `http://localhost:8501`.
   Confirm the sidebar shows **YOLO26n** and no red warning.
3. One site photo ready on the desktop (a construction photo with at least one worker).
4. Close anything that shows your webcam. The demo uses uploads, not the camera.
5. Breathe, stand still for one second, then begin.

---

## Slide 1 — Title · 0:40

> Good morning. My name is **JUNAID AHMAD**, registration number **12419395**, and this is
> my 471 project: **SiteGuard AI**.
>
> It is a computer-vision prototype that looks at construction-site footage and points out
> workers who **may** be missing protective equipment — a hard hat, a hi-vis vest, or
> gloves.
>
> The important word is **may**. This is decision support: the model suggests, and a person
> decides. And it runs entirely on **one laptop**, so no image ever leaves the machine.

*Delivery:* slow down on "may" — it is the theme of the whole talk. Do not read the slide.

---

## Slide 2 — The problem and the goal · 1:00

> Here is the problem. On a busy site, helmets, vests and gloves are easy to miss, and a
> supervisor cannot watch every camera every second. Manual checks only see the moments
> somebody happens to be looking.
>
> My idea was a camera model that looks at **every** frame and flags likely missing
> equipment on each worker.
>
> The principle matters more than the model: **the AI suggests, a person decides**. Nothing
> is called a violation on its own.
>
> The prototype delivers five things: it detects workers and twelve object types, checks
> helmet, vest and gloves per worker, records evidence, gives a human a review screen with
> a CSV report, and it is fully local.

*Delivery:* count the five deliverables on your fingers — the audience can follow.

---

## Slide 3 — How it works · 1:05

> Five steps. **Input** is a photo, a video file, or the live webcam.
>
> **Detect**: YOLO26n. YOLO is a real-time object detector — it draws a box around every
> object it recognises. Here that is people, PPE, and explicit missing-PPE boxes.
>
> **Check the rules**: the detector does not know who owns which helmet, so geometry links
> each box to one worker. A helmet must sit inside that person's body area.
>
> **Confirm**: a problem must appear in three analysed frames before it becomes an event,
> and repeats are suppressed for thirty seconds. One flicker does not raise an alarm.
>
> **Review**: the dashboard shows the evidence, and a person decides.

*Delivery:* the gold line under the steps is the point to make if you only have ten
seconds: "geometry decides who is tested, time decides whether an event exists."

---

## Slide 4 — The data · 0:55

> The data is the Ultralytics Construction-PPE dataset, released under **CC BY 4.0**,
> which means it can be used with attribution.
>
> One thousand labelled images: eight hundred for training, two hundred for validation.
> The validation set holds **2,961** labelled objects, so there is a real test to measure
> against.
>
> Twelve classes in three families. Gold: PPE that is present — helmet, vest, gloves,
> boots, goggles. Amber: explicit missing-PPE labels, drawn only on visible body parts.
> Slate: Person and forklift.
>
> The app requires helmet, vest and gloves.

*Delivery:* point at the amber bars in the class list when you say "visible body parts" —
it explains why occlusion is never treated as a violation.

---

## Slide 5 — Model and training · 0:55

> I started from **YOLO26n**, the smallest current Ultralytics model, already trained on
> general images, and fine-tuned it on these twelve classes. That is transfer learning: it
> keeps what it learned about shapes and edges, and I teach it the new classes.
>
> Thirty epochs — thirty passes over the training images — in **21 minutes** on this
> laptop's Apple GPU, at 640 pixels and batch eight.
>
> I chose the nano model for speed. A 30-frames-per-second camera gives you **33
> milliseconds** per frame. Inference takes about **20**. On a recorded replay of 149
> frames it analysed 29.8 per second and dropped none.

*Delivery:* these are **replay** numbers. Say the word "recorded" — it is honest and it
pre-empts the obvious question.

---

## Slide 6 — Accuracy · 1:10

> Now the honest accuracy — all on the 200-image validation split at 640 pixels.
>
> **Precision** is how often a detection is right: 0.832, so about eighty-three percent.
> **Recall** is how much labelled equipment it finds: 0.681.
>
> **mAP50** measures box quality when a box counts as correct at fifty percent overlap;
> mAP50-95 repeats that at stricter overlaps. Both are averaged over the twelve classes.
>
> The picture is clear. People and worn PPE are strong: Person 0.940, goggles 0.924, vest
> 0.887. The amber bars are the missing-PPE classes, and they are weaker: no_helmet 0.652,
> no_gloves 0.620, and no_goggle only 0.148 — which is why goggles are not required by
> default.
>
> At the app's operating confidence of 0.25, precision is 0.884 and recall 0.745.

*Delivery:* do not apologise for the amber bars. State them, then move on — slide 9 comes
back to them.

---

## Slide 7 — The bigger-model experiment · 1:10

> Would a bigger model fix the missing-PPE weakness? I tested that properly.
>
> **E3** is YOLO26m at 896 pixels. On the same 200 validation images it wins: mAP50 0.854
> against 0.734, recall 0.858 against 0.745.
>
> But that set also chose the model, so it flatters it. I then ran a **locked test**: 160
> images, 2,480 objects, used exactly once. E3 reached mAP50 **0.847** against a target of
> **0.93** set in advance. Precision 0.885 and recall 0.862, both short of 0.90.
>
> And it runs at 23.7 frames per second — dropping 31 frames — so it cannot analyse every
> frame of a 30 fps camera.
>
> It failed the accuracy gate and the speed budget. It is **not promoted**; YOLO26n stays
> active.

*Delivery:* this is the strongest part of the project. Say "the gates were written before
the test" clearly — it shows the result was not chosen afterwards.

---

## Slide 8 — The application and live demo · 2:20

### 8a. Talk (0:30)

> This is the application: eight pages, from Overview to Settings. The large image is the
> real Safety Events page, and the small one is Image Inspection.
>
> The list on the left is the review loop: upload a photo and you get boxes plus a status
> for each worker; every event is reviewed by a person; the live webcam runs at about
> thirty frames per second; and nothing leaves this laptop.
>
> Let me show you the image side.

### 8b. Live demo (1:50) — the exact clicks

Switch to the browser. Narrate while you click; never go silent.

1. *"I am on **Image Inspection**."* (sidebar, third item)
2. *"I upload one site photo."* Click the uploader, choose the photo.
3. Wait for the result (usually a second or two). Then: *"Here is the original, and here is
   the annotated result. Each box is a detection; the colour and the label say what it is."*
4. Scroll to **Compliance**. *"Below, the app lists each worker and each required item —
   helmet, vest, gloves — with its status. Potential violation, compliant evidence, or
   uncertain."*
5. Point at one card: *"This is decision support: the model proposes, and I can confirm or
   dismiss it."*
6. *"And the event is already recorded."* Go to **Safety Events**. *"Here it is, with the
   evidence frame, the confidence, and a review status I can change and export as CSV."*
7. Back to the deck.

*Recovery lines, if something fails:*
- Slow or spinning: *"While that runs — the detection is one forward pass of a small model,
  so a single image is normally under a second."*
- Wrong photo or no detection: *"Let me pick a clearer frame."* Reload the page if the
  uploader is stuck; the app keeps working.
- Dashboard not running: *"I will show the recorded result instead"* — use the screenshot
  on the slide and continue the script from step 4.

---

## Slide 9 — Limitations · 0:55

> I want to be direct about what the model cannot do.
>
> Missing-PPE recall is below 0.90 for **every** class: 0.615 for no_helmet, 0.567 for
> no_gloves, 0.171 for no_goggle. In plain words, it misses many real cases — so the system
> **under-reports** rather than over-reports.
>
> Real-site photos score 0.592 mAP50 against 0.951 on generated close-ups, so the headline
> numbers are flattered by easy images. An overhead camera view collapses to 0.185 against
> 0.639 frontal.
>
> 178 labels may be wrong and have not been reviewed. And this is a prototype on one public
> dataset — not a certified safety system.

*Delivery:* steady voice, no hedging. The honesty is the selling point.

---

## Slide 10 — Conclusion · 0:35

> To conclude. SiteGuard AI works today: a local real-time system at 29.8 frames per
> second, an eight-page dashboard with human review, an honest evaluation that includes a
> failed experiment, and 205 automated tests.
>
> The path forward is clear: more real-site and overhead data, a review of those 178
> labels, a faster large model so a bigger network fits the thirty-frames-per-second
> budget, and eventually multi-camera sites with worker tracking.
>
> The value here is not a perfect model. It is a complete, measured, honest system that a
> supervisor could actually use as decision support.
>
> Thank you. I am happy to take questions.

*Delivery:* stop talking, keep the slide up, and look at the teacher. Do not fill silence.

---

## If you are running long

| Cut | Saves |
|---|---|
| Demo step 6 (Safety Events) | 0:25 |
| Slide 4, second paragraph (chips detail) | 0:15 |
| Slide 5, transfer-learning explanation | 0:15 |
| Slide 8a (let the screenshots speak) | 0:15 |

## If you are running short *[if time]*

- **Slide 3:** "Every frame is one forward pass; the rules layer adds no model, just
  geometry and a timer."
- **Slide 6:** "The detector's confidence is a model score, not a calibrated probability —
  between 0.45 and 0.75 it is under-confident, with a calibration error of 0.107."
- **Slide 9:** "The 178 suspect labels matter because some of the measured error may be
  label noise, not model error."

## Ten phrases to have ready

1. "Decision support, not a safety certification."
2. "A missed detection produces no event, so silence is never proof of compliance."
3. "The gates were written before the test."
4. "That number is from the 200-image validation split."
5. "That one is from the locked test — 160 images, used once."
6. "The worker labels are per frame, not identities."
7. "Everything runs locally; no frame is uploaded."
8. "The model suggests; a person reviews."
9. "These are replay numbers, not a physical-camera test."
10. "It under-reports rather than over-reports."
