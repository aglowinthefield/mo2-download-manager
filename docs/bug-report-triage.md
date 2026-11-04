# Public bug-report triage

Initial triage baseline: `6cd739b` (the download action/state refactor). Sources were read live during this follow-up; issue closure is not treated as proof of a current fix.

Before opening the follow-up PR, `main` advanced to `ebd5e80`, merging PR #22. The follow-up is based on that updated `main`: it adds the dark-row fix and regression coverage for the already-merged metadata fixes, rather than duplicating their implementation.

## Coverage

- **GitHub (initial triage):** all 16 issues (4 open, 12 closed), all 13 issue comments, and all 5 pull requests (1 open, 1 closed unmerged, 3 merged) were reviewed. The latest published release returned was [v1.8.0](https://github.com/aglowinthefield/mo2-download-manager/releases/tag/v1.8.0), distinct from the baseline above.
- **Nexus:** confirmed [MO2 Download Manager Plus, Skyrim Special Edition mod 136003](https://www.nexusmods.com/skyrimspecialedition/mods/136003), by aglowinthefield, through the public [Nexus GraphQL endpoint](https://api.nexusmods.com/v2/graphql). The listing identifies version 1.8.0 and the `plugins/mo2-download-manager` directory.
- **Nexus coverage is incomplete:** the [Bugs tab](https://www.nexusmods.com/skyrimspecialedition/mods/136003?tab=bugs), [Posts tab](https://www.nexusmods.com/skyrimspecialedition/mods/136003?tab=posts), and homepage returned HTTP 403 Cloudflare challenges. No individual Nexus reports/comments, report counts, affected versions, or statuses were verified. A readable export or user-provided report text is needed; this is not evidence of zero bugs.
- No issues were posted, closed, or otherwise changed. No live Nexus credentials or downloads were used in regression tests.

## Actionable reports

### PR #22: queried metadata is written to the wrong INI section — merged; regression coverage added

Source: [.meta Querying fixes](https://github.com/aglowinthefield/mo2-download-manager/pull/22), by **EzioTheDeadPoet**.

Qt treats INI `[General]` as the root. Calling `beginGroup("General")` instead writes a literal group as `[%General]`, so MO2 does not see the queried values at the expected keys. The fix uses root keys, following the submitted PR. Existing unrelated values are retained; the operation does not sweep away legacy groups.

Regression: `tests/test_nexus_requery.py`, through `DownloadManagerModel.requery`, with real files/QSettings and a controlled HTTP response. Before the fix, reading root `modID` yielded **0**, not **1234**. After the fix, root IDs and the published download name agree. Existing root metadata is updated while installed/custom values survive.

### PR #22: wrong description source — merged; regression coverage added

The same [PR](https://github.com/aglowinthefield/mo2-download-manager/pull/22) reports that the entire mod-page BBCode is stored instead of the matched file description. The final PR uses `response.file_details.description`; its intermediate suggestion of the mod summary is not the intended fix.

Regression: the model-level re-query test first read `[b]Full mod-page description[/b]` instead of `Only this file's installation notes.`. The writer now uses the file description. The synthetic response in `tests/fixtures/nexus-md5.json` deliberately gives the mod description, mod summary, and file description different values.

### Issue #20: unreadable alternating rows in dark mode — reproduced and fixed locally

Source: [Alternate row colours show up as light text on a light background](https://github.com/aglowinthefield/mo2-download-manager/issues/20), with a [reporter screenshot](https://github.com/user-attachments/assets/c49106a6-4935-4883-be1b-73328812027c) and [maintainer acknowledgement](https://github.com/aglowinthefield/mo2-download-manager/issues/20#issuecomment-2758030129).

The report does not name the exact MO2 theme or versions. A representative reproduction uses the installed `dark.qss`, which sets global light text and a dark item-view background, but defines alternate colours only for tree/list views. A light inherited `AlternateBase` therefore leaks into the plugin table. Unchecked/unselected rows reproduce the problem; checkbox tint is not required. Extending the stylesheet selector in memory, or changing only the inherited alternate colour, independently removes the failure.

Rendered pixels under Fusion with a light fallback palette:

| Environment | Alternate text/background before | Contrast before → after |
| --- | --- | --- |
| Qt 6.12 / offscreen | `#e9e6e4` / `#f7f7f7` | **1.160:1 → 5.184:1** |
| Qt 5.15.2 / Windows | `#e9e6e4` / `#f7f7f7` | **1.160:1 → 5.162:1** |

The fix is local to the table's paint options: when the alternate background has poor contrast and the normal brush is readable, reuse the normal brush, including its gradient. This may remove visible striping for an incomplete theme; it does not change the saved alternation setting. Already-readable colours, selection/checkbox backgrounds, the host palette, and installed stylesheets are left alone. Fresh paint options follow later theme and parent-palette changes. The fallback does not attempt to interpret transparent or texture backgrounds or repair an already-unreadable normal background. Gradient safety uses conservative RGB bounds, not just endpoint contrast; ambiguous gradients are left alone.

Regression: `tests/test_table_theme.py` uses a self-contained minimal stylesheet, real Qt rendering, solid foreground-pixel sanity checks, and a 4.5:1 contrast threshold. It covers the broken theme, readable dark/light themes, same-table theme transitions, parent-palette propagation, disabled alternation, checked rows, and selected rows on both bindings. Separate installed-theme controls kept `1809 Dark Mode.qss` and `vs15 Dark.qss` unchanged on both bindings, and `Paper Dark.qss` unchanged on Qt6. The Qt5 Paper Dark solid-foreground sanity check did not pass, so that run is not counted as evidence.

This fixes a verified instance of the reported symptom, not a verified copy of the screenshot's exact theme. Host palette/platform details affect whether the omission is visible.

### Issue #5: distinct files selected as duplicates — needs original metadata

Source: [False duplicates](https://github.com/aglowinthefield/mo2-download-manager/issues/5), quoting a Nexus report about sothasimp furniture patches named **BOS Color Variance Use Those Blankets Patch**. The [closing comment](https://github.com/aglowinthefield/mo2-download-manager/issues/5#issuecomment-2557212416) says the maintainer could not replicate it; there is no linked fix or direct Nexus report URL.

The original archive IDs and `.meta` sidecars are absent. Do not change destructive duplicate-selection semantics on an invented reproduction. Ask for the affected sidecars/archives to establish which distinct files were incorrectly grouped.

## Verification

All **35 tests pass on each binding** in separate Python 3.12.15 environments: PyQt6 / Qt 6.12 and PyQt5 5.15.11 / Qt 5.15.2. The new tests exercise the public re-query operation and rendered tables, rather than asserting internal helper behavior. No plugin deployment or in-MO2 smoke test was performed for this follow-up.

## Historical reports, not newly confirmed defects

| Report | Evidence / disposition |
| --- | --- |
| [#1 sorting resets](https://github.com/aglowinthefield/mo2-download-manager/issues/1) | [PR #8](https://github.com/aglowinthefield/mo2-download-manager/pull/8) explicitly fixes it and was merged. The merge is in the baseline; current table tests also exercise sort/filter retention. |
| [#2 slow refresh](https://github.com/aglowinthefield/mo2-download-manager/issues/2) | Closing comment links [77f508f](https://github.com/aglowinthefield/mo2-download-manager/commit/77f508fcf07281b012aa215f10c972b9ff131eb8), included in baseline. No timings or new regression case supplied. |
| [#13 installed state of modified Engine Fixes TOML](https://github.com/aglowinthefield/mo2-download-manager/issues/13) | Closing comment links [a2320c9](https://github.com/aglowinthefield/mo2-download-manager/commit/a2320c901e8d184fcd6f03646250ca76ba850f31), included in baseline. No later regression case. |
| [#14 resizing is slow](https://github.com/aglowinthefield/mo2-download-manager/issues/14) | Maintainer says fixed, but no specific fix or benchmark is linked. Not independently performance-verified. |
| [#15 missing-field sorting](https://github.com/aglowinthefield/mo2-download-manager/issues/15) | Closed edge-case/enhancement request. Linked [PR #17](https://github.com/aglowinthefield/mo2-download-manager/pull/17) was not merged, and its linked diff does not clearly establish the sorting policy. Closure alone is not proof of implementation. |

## Feature requests kept separate

Open [#18 missing download archives](https://github.com/aglowinthefield/mo2-download-manager/issues/18), [#19 downloading current versions](https://github.com/aglowinthefield/mo2-download-manager/issues/19), and [#21 unattended installation/FOMOD ordering](https://github.com/aglowinthefield/mo2-download-manager/issues/21) describe new workflows, not confirmed malfunctions.

Other closed requests reviewed: [#3](https://github.com/aglowinthefield/mo2-download-manager/issues/3), [#4](https://github.com/aglowinthefield/mo2-download-manager/issues/4), [#6](https://github.com/aglowinthefield/mo2-download-manager/issues/6), [#11](https://github.com/aglowinthefield/mo2-download-manager/issues/11), [#12](https://github.com/aglowinthefield/mo2-download-manager/issues/12), and [#16](https://github.com/aglowinthefield/mo2-download-manager/issues/16). No new bug was established from those requests.
