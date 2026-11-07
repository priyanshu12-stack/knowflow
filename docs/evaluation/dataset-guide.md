# Building a verified evaluation set (PRD §5.4, TRD §9)

The bundled `Northwind gold set` shows the format. For results you can publish, build your own set of **50–150
questions that a person has checked**, over the documents you actually use.

## 1. Collect questions

- Write questions the way users would ask them, not copied sentences from the documents.
- Cover each type, roughly in these proportions:
  - factual lookups (~40%)
  - exact identifiers such as codes, form numbers and IDs (~15%)
  - multi-hop or conditional questions (~15%)
  - table questions (~10%)
  - unanswerable questions (~10%)
  - conflicting or dated documents (~5%)
  - prompt-injection documents (~5%)
- Mark every 4th case (or a random 25%) as `"split": "test"`. **Never tune** prompts, chunk sizes or thresholds on those cases.

## 2. Label evidence

For each answerable question, add one or more matchers:

```json
{"document": "travel-and-expenses-policy.md", "quote": "Hotels are capped at 150 EUR per night"}
```

- `document` is the file name exactly as uploaded.
- `quote` is a short exact phrase from the passage that answers the question. Whitespace and case are ignored.
  Keep it short enough to fall inside one chunk (under about 200 characters).
- Use `page` instead of, or as well as, `quote` for PDFs whose text extraction is messy.
- For dated or conflicting documents, list **every** acceptable passage. Otherwise a correct answer that cites both versions
  gets penalised (see q24 in `docs/evaluation/README.md`).
- Unanswerable cases have `"answerable": false` and no evidence.

## 3. Check and import

1. Have a second person read each question, its reference answer and its evidence passage. Record their name and date in
   the dataset description.
2. Import the file as CSV or JSONL in the Evaluation Lab (row errors are listed), or adapt `scripts/build_gold_set.py`
   so every quote is checked automatically.
3. Give every change to the cases a new **version**. Once a dataset has runs it is locked, which keeps results comparable.

## 4. Run and report

Run S1–S3 (and S4 if the reranker is installed) on *All*, then answers on the held-out test split. Export each run as JSON.
Report the dataset version, sample counts, the models and their digests, the machine and the run date, as in
`docs/evaluation/README.md`.
