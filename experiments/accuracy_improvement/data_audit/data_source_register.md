# Data-source register (specification §5.1)

**Assessed:** 2026-11-20, using a web search (no data was downloaded or uploaded).
**Rule:** nothing is imported until this register records dataset, source, licence, download date, version, hashes, class mapping and limitations, and the dataset passes the checks below.

## Import checks applied

1. **Clear licence** compatible with academic use and with the CC BY 4.0 project data.
2. **Clear provenance:** who collected or generated the images; no images scraped under unclear rights.
3. **Class semantics** that map onto all 12 SiteGuard classes. In particular, every image must be **exhaustively labelled for all 12 classes**. Ultralytics detection training has no per-image "unlabelled class" mask, so a missing label teaches the model that the object is background.
4. **Label quality:** reviewed annotations consistent with `docs/ANNOTATION_POLICY.md`.
5. **No overlap with the current 1,000 images.** This is checked by hash and embedding before import, so that the locked test cannot leak.

## Register

| # | Dataset | Source | Licence (as published) | Version / size | Classes vs SiteGuard 12 | Decision | Reason |
|---|---|---|---|---|---|---|---|
| 0 | **Ultralytics Construction-PPE** (the project dataset) | `../construction-ppe/` (local); [Ultralytics blog](https://www.ultralytics.com/blog/missing-ppe-detection-yolo) | CC BY 4.0 (local `LICENSE.txt`) | Nov 2026 release: 1,000 images, 14,863 boxes, 12 classes | Identical | **In use**, read-only | — |
| 1 | Ultralytics Construction-PPE, **earlier documented version** | [docs.ultralytics.com/datasets/detect/construction-ppe](https://docs.ultralytics.com/datasets/detect/construction-ppe) | Listed as **AGPL-3.0** in the docs search result. This conflicts with the CC BY 4.0 of the current release | 1,416 images (1,132 / 143 / 141), 11 classes | Has helmet, gloves, vest, boots, goggles, Person and no_helmet / no_gloves / no_boots / no_goggle, plus a generic `none`. **No `no_vest`, no `forklift`** | **Not imported** | (a) No-vest workers and forklifts are unlabelled, so they would become background (check 3). (b) Same creator: likely image overlap with the current release, a leakage risk for the locked test (check 5). (c) The licence conflict is unresolved (check 1). (d) Superseded by the reviewed and corrected release (check 4) |
| 2 | **SH17** (Ahmad & Rahimi, J. Safety Science and Resilience 2024) | [GitHub](https://github.com/ahmadmughees/SH17dataset), [arXiv 2407.04590](https://arxiv.org/abs/2407.04590), [Zenodo](https://zenodo.org/records/12659325) | **CC BY-NC-SA 4.0**; the Zenodo record is "restricted"; images are from Pexels, whose terms also apply | 8,099 images, 75,994 instances, 17 classes | person, head, face, glasses, face masks, face guard, ear, earmuffs, **hands**, **gloves**, **foot**, **shoes**, safety vest, tools, helmet, medical and safety suits. **No missing-PPE classes**: "hands" and "head" are not "no_gloves" and "no_helmet" by definition; "glasses" are not protective goggles; "shoes" are not safety boots. No forklift | **Not imported** | The mapping to the five missing-PPE classes would need re-labelling (check 3). Non-commercial share-alike licence with additional image terms (check 1). Industrial scenes outside construction |
| 3 | Roboflow Universe datasets (for example "Worker-Safety": helmet, vest, person, no-helmet, no-vest) | [universe.roboflow.com](https://universe.roboflow.com/container-saxdh/worker-safety-pe3ls) and similar | Varies by dataset; not shown in the search results; provenance often undocumented | Varies | At most 5 of the 12 classes; no gloves, boots or goggles (or their missing classes), no forklift | **Not imported** | Partial labels (check 3); unclear licence and provenance (checks 1–2) |

## Conclusion

**No external dataset meets the import checks.** All candidates fail on partial class coverage. Their unlabelled SiteGuard classes would be learned as background, which would directly harm the safety-critical missing-PPE classes. Most also have licence or provenance problems.

Following spec §5.1, the programme **proceeds with the existing verified data** and records this as a limitation.

A future import would need full re-annotation to the 12-class policy and a deduplication against the current 1,000 images (hash and embedding). Collecting and labelling **independent deployment imagery** (real site cameras) would also give the independent test set the dataset README recommends.
