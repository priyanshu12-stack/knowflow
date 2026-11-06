# ADR-005: Chunking strategies (fixed baseline + recursive structure-aware)

- Status: Accepted for M2. The *default* is provisional until the M5 evaluation compares S1 vs S2.
- Milestone: M2

## Context

TRD §9 needs two chunk sets to compare on the same corpus: S1 (fixed-size) and S2 (recursive /
structure-aware). Citations must point at pages or headings (PRD §5.2), so every chunk needs a
page range and section path. The machine embeds on CPU, so chunk count has a real cost.

## Decision

- Extraction produces ordered *units*: one per PDF page, one per DOCX/Markdown heading section,
  or the whole TXT file. Units are stored in `document_sections` so the extracted text stays
  inspectable.
- **fixed**: concatenate units and cut 1,200-character windows with a 200-character overlap,
  snapping to whitespace so words aren't cut. It may cross page/section boundaries (page_start <
  page_end). This is the naive baseline.
- **recursive**: never crosses a unit boundary. It splits on `\n\n`, `\n`, `. `, then spaces, and
  greedily merges pieces back up to 1,200 characters, with no overlap.
- Both strategies are generated for every document so S1 and S2 can be evaluated without
  re-ingesting. The library shows the **recursive** chunk count, and retrieval uses
  `recursive` by default.
- Sizes are measured in characters. `token_count` is an estimate (characters / 4) because the
  embedding model's tokenizer isn't available offline. Settings: `CHUNK_SIZE_CHARS`,
  `CHUNK_OVERLAP_CHARS`.
- Semantic chunking (TRD §3, an experiment) is not built. It needs embeddings per sentence, which is
  expensive on this CPU, and there's no measured need yet.

## Consequences

- Storing two chunk sets doubles chunk rows and embeddings. That's acceptable at local-library
  scale, and the M5 results will decide whether it's worth keeping both.
- Page-level citations are exact for recursive chunks. A fixed chunk reports a page *range*.
- TXT files have only document-level citation granularity, and the UI says so.
