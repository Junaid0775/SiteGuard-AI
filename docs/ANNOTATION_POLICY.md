# SiteGuard AI — Annotation Policy

**Version:** 1.0 (2026-11-20). Created in Phase 1 of the YOLO26m accuracy-improvement programme (REPORT-019).
**Applies to:** any correction, re-labelling or new labelling done for SiteGuard AI, and to the review of the existing labels.

## 1. Status and provenance

The source dataset (Ultralytics Construction-PPE, November 2026, CC BY 4.0) does not publish a full annotation guideline. Its README states only:

- that its annotations combine "expert human annotation and AI auto-annotation" and that "all images and annotations were reviewed and corrected";
- one labelling rule: **"Missing-PPE labels refer to visible body regions; occlusion alone is not evidence of missing equipment."**

Everything else in this document is the **SiteGuard project's own policy**. It is written to make labels consistent and the compliance logic safe. **It does not claim to reproduce the dataset creator's intent.**

Where existing labels differ from this policy, they are kept unchanged in the original dataset (which is read-only). They are listed for human review. Any correction is applied only in a versioned derived copy (§10).

## 2. General rules (all classes)

1. **One box per visible object instance.** The box is tight around the *visible* extent of the object, at native image resolution.
2. **Same object, same class:** two boxes of the same class with IoU ≥ 0.8 are duplicates. Keep one.
3. **Truncation:** an object cut by the image border is labelled on its visible part if it is still identifiable.
4. **Occlusion:** label the visible part of an object if it is identifiable. **Never infer a missing item from occlusion.**
5. **Judgeability:** a label is given only when a careful human looking at the native-resolution image can decide the class. If the state of an item cannot be decided, give no item label (see §6 and §9). Audit evidence: 2,207 of 14,863 existing boxes have a short side under 8 px at the 640 inference size, but only 36 are under 8 px at native resolution. Most existing labels are judgeable at native resolution; it is the 640 down-scaling that makes them tiny.
6. **Positive and missing items are mutually exclusive per body region and person.** One head cannot be both `helmet` and `no_helmet`. Hands and feet are separate regions (one gloved hand and one bare hand is valid).

## 3. Class definitions

| ID | Class | Definition | Box extent | Do not label |
|---:|---|---|---|---|
| 0 | helmet | Hard hat or safety helmet **worn on the head** | The helmet shell (brim included) | Caps, beanies, hoods, hair nets; helmets that are not worn (§8.4) |
| 1 | gloves | Work or protective glove worn on a visible hand | Each gloved hand separately | Bare hands; gloves lying on surfaces |
| 2 | vest | High-visibility vest or hi-vis jacket worn on the torso | The visible vest/jacket area | Ordinary coloured clothing without reflective/hi-vis design |
| 3 | boots | Safety or work boots on a visible foot | Each boot separately | Feet that are not visible; trainers or sandals (these are `no_boots` if the foot is visible) |
| 4 | goggles | **Protective** eyewear on the eyes: safety goggles, or safety glasses with a wraparound or side-shield design | The eyewear | Ordinary prescription glasses and sunglasses (§7) |
| 5 | Person | A human whose body is visible enough to recognise as a person | The **full visible extent of the person, including head, raised arms, hands and feet** (§4) | Reflections, posters, mannequins |
| 6 | no_helmet | Head visible and resolvable, and no helmet on it | The head | Heads that are hidden, turned away beyond judgement, or too small to judge |
| 7 | no_goggle | Eye region visible and resolvable, with no protective eyewear | The eye band | Unresolvable or hidden eyes; back-facing people (§6) |
| 8 | no_gloves | Hand visible and resolvable, without a glove | Each bare hand | Hands hidden in pockets, behind objects, or too small to judge |
| 9 | no_boots | Foot visible and resolvable, without safety footwear | Each foot | Feet that are hidden or unresolvable; ambiguous leather shoes (§9) |
| 10 | forklift | A forklift truck (any counterbalance or reach truck) | The whole visible vehicle | Other vehicles: excavators, rollers, trucks |
| 11 | no_vest | Torso visible and resolvable, without any hi-vis vest or jacket | The torso | Torsos hidden by objects or other people |

## 4. Person boxes

- **Include the full visible extent of the person.** The current dataset often has *tight* Person boxes that leave out raised arms, reaching hands, heads (in one hazy warehouse image, systematically) or feet.
  - This is the main reason for the 51 high-priority audit flags (REPORT-019).
  - With the compliance analyser's 10 % person-box margin, 42 of those 51 boxes do associate with a person; with a 25 % margin, 49 do.
  - New or corrected Person boxes should include the limbs.
- **Partially visible people** get a Person box on their visible part when any of these is visible and recognisable: the head and shoulders, the torso, or about a third of the body.
  - A lone hand or foot entering the frame gets **no** Person box.
  - Its item label (for example `gloves`) may still be given if the item is identifiable.
- **Overlapping people:** each person gets their own box even when the boxes overlap.

## 5. Missing-PPE labels — when they are justified

A `no_*` box is justified only if **all** of these hold:

1. The body region (head, eyes, hands, torso or feet) is **visible** in the image (dataset rule: occlusion is not evidence of missing equipment).
2. The region is **resolvable** at native resolution: a careful human can see that the item is absent.
3. The region belongs to a **visible person**, and that person should have a Person box (§4).
4. No positive label exists for the same region of the same person.

**What a `no_*` label means:**
- It means "this region is visible and the item is absent".
- It does **not** mean "the site rule is violated".
- Which items a site requires is configured in the application (`compliance.required_ppe`), not in the labels.

## 6. Eye region: unresolvable eyes

- Give no `goggles` and no `no_goggle` label when the eyes are:
  - not visible (back-facing person, eyes covered by a visor or hair, head turned away);
  - too small to judge (in practice, an eye band only a few pixels high at native resolution).
- Audit context:
  - 54.9 % of the 2,443 Person boxes have neither an eye label, a goggles label nor a no_goggle label.
  - 99.7 % of no_goggle boxes cover under 1 % of the image area.
  - At 640 inference, the median short side of a no_goggle box is 9.4 px.
- **Earlier visual review:** no_goggle was found on distant workers whose eyes cannot be resolved. Those labels conflict with this rule and are listed for human review. They are **not** removed automatically.

## 7. Ordinary eyeglasses versus protective goggles

- **Protective eyewear (`goggles`):** safety goggles; safety glasses with wraparound lenses or side shields; welding goggles worn over the eyes.
- **Ordinary prescription glasses and sunglasses** are *not* protective eyewear. A person wearing only those, with the eyes visible and resolvable, is `no_goggle`. This matches the existing labels found in REPORT-010.
- **When the eyewear type cannot be decided** (for example clear glasses with no visible side protection at low resolution): give no eye label, and record the case as `uncertain` in a review.

## 8. Special situations

### 8.1 Forklift and vehicle operators

- An operator visible in a cab is a **Person**: label the visible part, usually head and torso.
- Label items and missing items only for **visible, resolvable** regions. Do not label legs or feet hidden by the cab as `no_boots`.
- **Known inconsistency in the existing labels:** forklift drivers are usually *not* labelled as Person, while a road-roller driver *was* labelled with no_helmet. Existing labels are unchanged; the cases are listed for human decision.
- Whether operators must wear a helmet is a **site rule**. It is not a labelling question.

### 8.2 Tiny, occluded or unjudgeable PPE

- **Positive PPE:** label it if it is identifiable at native resolution.
- **Missing PPE:** label it only if absence is clearly visible (§5). When in doubt, give no label and record the case as `uncertain`.
- Objects below about 8 px on their short side at native resolution are treated as **not judgeable** for missing-PPE labels.

### 8.3 Overlapping workers and boxes

- Assign each item to the person who wears it.
- If an item could belong to two overlapping people, still label it, and record "ambiguous association" in the review notes.
- The application handles ambiguous associations conservatively (status *uncertain*).

### 8.4 Unworn items

- A helmet on the ground or a vest on a rack is not worn PPE.
- **Project policy for new labels:** do not label unworn items.
- **Existing labels:** the dataset contains at least one unworn helmet labelled `helmet` (review case N013). It stays unchanged pending human decision. Unworn items cannot create compliant evidence at runtime anyway, because association requires containment in a Person box.

## 9. Uncertain and excluded examples

- **Review statuses** (spec §3.2): `unreviewed`, `confirmed`, `corrected-in-derived-copy`, `exclude-with-reason`, `uncertain`.
- **Only a human reviewer can set a review status other than `unreviewed`.**
- AI-assisted assessments are recorded in separate columns. They are never presented as human review.
- **Excluding a label** in a derived copy turns that object into background for training. If it is a real object, that teaches the model to ignore it.
  - Prefer **excluding the whole image** from an evaluation set when its ground truth cannot be judged.
  - Prefer **keeping** a plausible label in training data unless a human decides otherwise.
- **Ambiguous footwear** (for example leather shoes that look like work boots): do not label, or record as `uncertain`.

## 10. Change control

1. The original dataset (`../construction-ppe/`) is never edited.
2. Corrections live only in a **versioned derived copy** under `experiments/accuracy_improvement/`, with:
   - a change log (source annotation ID, old label, new label, reason, reviewer, timestamp);
   - SHA-256 hashes of every changed label file.
3. **Evaluation labels** (development and locked-test sets) change only after human review. Any metric on corrected labels is reported next to the metric on the original labels.
4. Annotation IDs use the form `<split>/<label stem>#L<row>`, where row is the 1-based index among the non-empty lines of the label file.

## 11. Compliance interpretation (critical)

- **The absence of a PPE detection is not proof of a violation.**
- The application raises a *potential violation* only from an explicit missing-PPE detection (`no_*`) with confidence ≥ 0.50, associated with a detected person.
- Missing or ambiguous evidence gives the status *uncertain*.
- This policy does not change that logic (`configs/settings.yaml → compliance`). Any change to it needs separate approval.
