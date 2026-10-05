# Stale remote branches (inventory)

Generated for the burden-reduction pass. Open PR heads are **not** deleted.

## Keep (open / related)

- `b-team/ui-redesign-f8dc` — PR #136 (draft; do not delete)
- `cursor/eng-loop-895b` — PR #132 (draft; do not delete)
- `cursor/logbridge-ui-895b` — local UI loop companion to #132; keep until #132 closes

## Screenshot CI

`main` workflow (`.github/workflows/test.yml`) has **no** screenshot job.
Team B’s screenshot baseline lives only on `b-team/ui-redesign-f8dc` and is
already non-blocking for render failures there. No change required on `main`
for “screenshot checks must not block CI”.

## Merged into main (candidates to delete)

- `cursor/acesotnote-zh-inspector-wb-0935`
- `cursor/batch-export-locked-clips-376f`
- `cursor/clip-export-chip-022b`
- `cursor/clip-reveal-finder-f4f2`
- `cursor/export-10bit-first-48de`
- `cursor/export-check-exr-resolve-131b`
- `cursor/export-disk-space-9c59`
- `cursor/export-folder-finder-6f18`
- `cursor/export-progress-cancel-de88`
- `cursor/exr-adopted-neutral-5359`
- `cursor/failure-chip-copy-44ce`
- `cursor/failure-notes-specific-d7b9`
- `cursor/full-clip-proxy-sequence-9b0d`
- `cursor/full-res-native-write-afca`
- `cursor/hdr-preview-colorsync-a243`
- `cursor/interaction-cleanup-locked-idt-c50d`
- `cursor/logc3-ei800-apple-log2-awg-836e`
- `cursor/macos-ci-swift-pytest-d72f`
- `cursor/post-batch-summary-b1a3`
- `cursor/preview-frame-scrubber-29a4`
- `cursor/preview-large-inspector-thin-137b`
- `cursor/readme-resolve-honesty-e7d0`
- `cursor/resolve-export-zh-honesty-a0ee`
- `cursor/resolve-handoff-locked-34fa`
- `cursor/source-labels-zh-0b16`
- `cursor/ui-preview-inspector-sidebar-e140`
- `cursor/usability-copy-953d`
- `cursor/verify-proxy-frame-count-43e0`
- `cursor/zh-fail-proxy-exr-1046`
- `cursor/zh-ui-copy-leftovers-5972`
- `m1-aces-ap0`
- `m1-asshot-wb`
- `m1-auto-wb-estimate`
- `m1-exposure-stops`
- `m1-format-compat`
- `m1-hlg-pq`
- `m1-idt-batch2`
- `m1-preview-perf`
- `m1-relative-cat`
- `m1-review-fixes`
- `m1-ui-intuitive`
- `m1-ui-polish`
- `m1-ui-usability`
- `m1-zh-settings`

## Deletion status

Merged-into-main candidates are deleted in this PR pass using a write-capable
token. Open PR heads (`b-team/ui-redesign-f8dc`, `cursor/eng-loop-895b`) and
`cursor/logbridge-ui-895b` are retained.

Deleted in this pass: **44** (failed: 0).
