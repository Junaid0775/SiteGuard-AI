# SiteGuard AI — Q&A cheat sheet

Twelve questions a teacher is most likely to ask, with answers based only on the project's
own files. Two to three sentences each: say the answer, give one number, stop.

---

**1. What is mAP?**

Mean average precision: for each class, you take the precision–recall curve and compute the
area under it, then average over the twelve classes. The "50" in mAP50 means a predicted box
counts as correct when it overlaps the true box by at least 50 %; mAP50-95 averages that over
overlap thresholds from 0.50 to 0.95, so it rewards tighter boxes. Our YOLO26n scores 0.734
mAP50 and 0.523 mAP50-95 on the 200-image validation split (`docs/EVALUATION.md` §1, §4).

**2. Why YOLO26n and not a bigger model?**

Because the job is live video: a 30 fps camera gives 33 ms per frame, and YOLO26n takes about
20 ms, so it analyses every frame and dropped none in a 149-frame replay. I did test the
bigger option — YOLO26m "E3" at 896 px reached mAP50 0.847 on the locked test, but the
pre-registered target was 0.93 and it ran at 23.7 fps, dropping 31 frames. It failed the
accuracy gate and the speed budget, so it was not promoted (`REPORT-025` §1, §8).

**3. How do you avoid false alarms?**

Three layers. A missing-PPE box needs confidence ≥ 0.50 before it can raise a potential
violation, the problem must persist for 3 analysed frames, and repeats of the same worker
region are suppressed for 30 s. On top of that, a `no_*` detection contradicted by a stronger
overlapping PPE box becomes *uncertain*, not a violation (`configs/settings.yaml`
`compliance`/`events`; `docs/ARCHITECTURE.md` §3–4).

**4. Is it safe to rely on this?**

Not as a safety control — and the project says so on the dashboard and in the README. It is
decision support: every event is a *potential* issue for a human to confirm, and missing-PPE
recall is below 0.90 for every class, so it under-reports. Absence of events never proves a
site is compliant (`README.md` §14).

**5. What data did you use?**

The Ultralytics Construction-PPE dataset, November 2026, CC BY 4.0: 1,000 labelled images,
800 train / 200 validation, 14,863 boxes in 12 classes. The validation split has 2,961
objects, and I never modified the original files — they are checksum-verified
(`docs/DATASET.md` §1–5).

**6. What would you improve next?**

First, a human review of the 178 suspect labels, because some measured error may be label
noise. Then consented real-site and overhead footage as a new independent test set, plus
multi-object tracking so worker IDs persist and a compliance rate becomes defensible
(`REPORT-025` §11, `README.md` §15).

**7. How does the live camera work?**

The browser captures frames and sends them to the local Streamlit server over WebRTC; a
worker thread runs the detector, draws boxes, and streams the annotated video back. Frames
are processed locally and nothing is uploaded — no STUN/TURN server is contacted. In the
replay test it handled 29.8 fps with 0 dropped frames (`docs/ARCHITECTURE.md` §6,
`README.md` §11).

**8. Where is the data stored?**

In one local SQLite file, `outputs/siteguard_events.db`, with an `events` table (category,
confidence, worker box, media time, evidence path, review status, notes) and an `inspections`
table. Evidence frames are JPGs in `outputs/evidence`; raw uploads are deleted after
processing (`docs/ARCHITECTURE.md` §5).

**9. What is the difference between precision and recall here?**

Precision is how often a detection is right — 0.832 on validation, so about 83 % of boxes are
correct. Recall is how much of the labelled equipment it finds — 0.681, so it misses about a
third. At the app's operating confidence of 0.25, precision rises to 0.884 and recall to 0.745
(`experiments/evaluation/trained_best/metrics.json`;
`evaluation/dev_yolo26n_active_baseline/summary.json`).

**10. Why is no_goggle so weak, and what do you do about it?**

The class has only 265 training boxes and the eye region is often a few pixels high, so it
scores 0.148 mAP50 and 0.171 recall. Because a weak class would create noise, goggles are not
in the default required-PPE list — the app checks helmet, vest and gloves
(`docs/DATASET.md` §4, `docs/EVALUATION.md` §4, `configs/settings.yaml`).

**11. How did you test the software?**

205 automated tests, collected with `pytest --collect-only` and restricted to `tests/` by
`pytest.ini`. They cover dataset parsing, the model registry and fallback, compliance and
deduplication, SQLite review and CSV export, real image and video inference, live frame
synchronisation (no stale boxes) and all 8 dashboard pages via Streamlit's AppTest.

**12. Could this run on real CCTV or several cameras?**

Not yet. There is a placeholder `OpenCVFrameSource` that accepts a stream URL, but RTSP input
is future work and there is no identity tracking, so multi-camera counting is not supported.
Overhead CCTV-style views are also the weakest case: mAP50-95 falls from 0.639 frontal to
0.185 overhead (`README.md` §13.2, `docs/EVALUATION.md` §5.1).

---

## Numbers you can quote without checking

| Question | Answer |
|---|---|
| Training time | 1,273 s ≈ 21 min, 30 epochs, 640 px, batch 8, Apple M5 GPU |
| Validation size | 200 images, 2,961 objects |
| mAP50 / mAP50-95 | 0.734 / 0.523 |
| Precision / recall | 0.832 / 0.681 |
| At confidence 0.25 | precision 0.884, recall 0.745 |
| Live replay, YOLO26n | 29.8 fps, 0 dropped, 20.3 ms mean, 24.8 ms p95 |
| E3 locked test | mAP50 0.847 (target 0.93), 160 images, 2,480 objects |
| E3 speed | 23.7 fps, 31 of 149 frames dropped |
| Tests | 205 collected |

## If you don't know

Say: *"That is not something I measured, so I would not want to guess — but the project's
evaluation report covers what I did measure."* Then name the report. Never invent a number;
every figure in the deck is in `FACTS.md` with its source.

## Five things not to say

1. "It guarantees safety" — it is decision support.
2. "It is production-ready" or "certified".
3. "93–95 % accuracy" — that target was **not** met (0.847 mAP50 on the locked test).
4. "Compliance rate" — there is no identity tracking, so no valid denominator exists.
5. "It works on any site camera" — real-site photos scored 0.592 mAP50 against 0.951 on
   close-ups.
