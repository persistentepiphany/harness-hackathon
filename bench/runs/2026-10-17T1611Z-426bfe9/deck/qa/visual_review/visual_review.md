# Visual Review Packet

- PPTX: `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/results/deck.pptx`
- Rendered slides: 8
- Warnings: 1
- Info: 13
- Contact sheet: `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/visual_review/contact_sheet.jpg`

## Findings

- [INFO] slide 1 / shape-7: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 2 / shape-11: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 2 / shape-12: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 3 / shape-7: text_box_tight - Estimated text height uses 93% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.
- [INFO] slide 3 / shape-12: text_box_tight - Estimated text height uses 92% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.
- [INFO] slide 3 / shape-15: text_box_tight - Estimated text height uses 92% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.
- [INFO] slide 4 / shape-7: text_box_tight - Estimated text height uses 93% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.
- [INFO] slide 4 / shape-10: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 4 / shape-13: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [WARNING] slide 5 / shape-7: text_box_clip_risk - Estimated text height is 172% of its box height.
  Suggestion: Increase the box height, reduce body copy, or reduce font size.
- [INFO] slide 5 / shape-14: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 6 / shape-17: body_font_small - Body-like text is 9.0pt.
  Suggestion: Check readability; use larger text or split dense content if this is not a table/caption.
- [INFO] slide 8 / shape-13: text_box_tight - Estimated text height uses 90% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.
- [INFO] slide 8 / shape-16: text_box_tight - Estimated text height uses 90% of its box.
  Suggestion: Check the rendered slide for clipping or awkward wrap.

## Rendered Slides

1. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-01.jpg`
2. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-02.jpg`
3. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-03.jpg`
4. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-04.jpg`
5. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-05.jpg`
6. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-06.jpg`
7. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-07.jpg`
8. `/home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/deck/qa/renders/slide-08.jpg`

## Human/Agent Review Checklist

- Inspect the contact sheet first for rhythm, density, and repeated layouts.
- Open individual slides for title wrapping, orphan words, weak contrast, and footer clearance.
- Fix `outline.json`, `design_brief.json`, assets, or renderer code, then rebuild.
- Do not patch the generated `.pptx` directly unless the task is an explicit one-off edit.
