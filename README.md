# PRISM (Personal Relational Intelligent Search Machine)

> **Status:** Planning complete. Development is about to begin with Sprint 1.

---

## Overview

PRISM is a study tool and web application where users can upload PDFs and search through them using plain English via semantic vector search. It combines a conversational search experience with relational metadata, Neo4j topic graphing, and a full inline document reader to help students retrieve specific concepts quickly under pressure.

## Current Status

Planning and documentation are complete. The product requirements, architecture, API contract, sprint breakdown, and UI references are finalized. The work has been divided into 23 vertical slices across two developers (Dev A and Dev B). Implementation has not started yet.

* **Version:** `0.1.0-dev`
* **Development Phase:** Sprint 1 — Foundation

## Upcoming Milestones

* **Sprint 1:** Foundation (Infra, DB Schema, Auth)
* **Sprint 2:** Document pipeline (Uploads, chunking, pgvector embedding)
* **Sprint 3:** Search (Semantic search, FULLTEXT fallback, Redis cache)
* **Sprint 4:** Graph and analytics (Neo4j topics, search analytics)
* **Sprint 5:** Frontend UI wiring (Next.js)
* **Sprint 6:** Polish and deployment (OCI VM & Vercel)

---

*Planning docs live in `docs/`.*
