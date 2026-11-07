---
title: KnowFlow
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
startup_duration_timeout: 1h
pinned: false
short_description: Local-model RAG with cited answers and safe text-to-SQL
---

# KnowFlow

**Answers grounded in your knowledge.** Ask questions about documents and get answers with verified,
clickable citations, ask business questions of a database through safe read-only SQL, and measure
retrieval quality in an evaluation lab.

This Space runs the whole app on free CPU hardware. The AI models (`qwen3:4b` and
`nomic-embed-text:v1.5`) run **inside the container** through Ollama, so no paid API is called.

- **Source code and full documentation:** https://github.com/priyanshu12-stack/knowflow
- **Developer:** Priyanshu Raj Mishra, B.Tech (ECE), BIT Mesra

## Things to know about this demo

- **It's slow.** Answers are generated on 2 shared CPU cores and take about 1–3 minutes.
- **Data is temporary.** The free Space disk is wiped on every restart. The sample documents,
  50-question gold set and synthetic sales database are reloaded automatically at startup.
- **It sleeps.** After about 48 hours without visitors the Space pauses; the next visit wakes it up
  (allow a few minutes).
