# cull-marks — shared XMP fixture corpus (copied for W109)

Copied **verbatim** from the Theia platform repo so the Python generator's XMP
writer is tested against the same bytes as the TypeScript writer (W109 plan
§5.1; contract `docs/implementation/handoffs/W109-cross-repo-image-generator.md`).

- Origin: `~/PLATFORM/theia-platform/test-fixtures/cull-marks/`
- Rebuild upstream with: `node generate-fixtures.js` (a copy is included here)
- Files: `unmarked.png`, `recipe.png`, `marked.png`, `reinject.png` plus the
  expected packet bytes `recipe.expected.xmp`, `marked.expected.xmp`,
  `reinject.expected.xmp`.

Do not edit these copies by hand; refresh them from the origin. The test
`tests/test_w109_cull_marks.py` asserts the copies stay byte-identical to the
origin when that path is present.
