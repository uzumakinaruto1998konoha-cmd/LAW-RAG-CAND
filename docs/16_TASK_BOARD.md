# 16. Task Board

| Phase | Epic | Task | Status | Priority | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|---|
| PHASE 0 | Baseline | Tạo bộ đặc tả ban đầu | Done | P0 | — | 18 tài liệu + state; liên kết yêu cầu/kiến trúc |
| PHASE 0 | Review | Rà soát consistency, conflict, dependency | Done | P0 | Baseline | Findings được ghi; không code |
| PHASE 0 | Decisions | Chốt TBD và phê duyệt baseline | Done | P0 | Review | Project owner xác nhận Phase 0 baseline được chấp thuận trong phiên 2026-09-26; TBD chưa thuộc ingestion vẫn tiếp tục theo Decision Log |
| PHASE 1 | Ingestion design | Chốt formats, giới hạn, OCR/parser và lưu trữ | Done | P0 | Phase 0 approval | Lựa chọn ingestion v1, ngưỡng review và corpus manifest được ghi ở docs/05, ADR-004..006, docs/13 |
| PHASE 1 | Ingestion engine | Upload, hash, validation, job lifecycle | Pending | P0 | Ingestion design | Idempotent, audit, lỗi an toàn |
| PHASE 1 | Extraction | PDF/DOCX/text/image extraction và OCR | Pending | P0 | Ingestion engine; OCR decision | Page mapping, confidence, review path |
| PHASE 1 | Legal parsing | Metadata + hierarchy + relation candidates | Pending | P0 | Extraction; legal schema | Node/provenance/confidence; reviewer workflow |
| PHASE 1 | Release to KB | Approval, dedup, version and processing run | Pending | P0 | Legal parsing; schema | Bản chưa duyệt không được retrieve |
| PHASE 2 | Knowledge model | Implement document/legal schema and ACL | Pending | P0 | Phase 1 design; decisions | Version/time/history constraints |
| PHASE 2 | Knowledge UI/API | Manage document, metadata, version, relation | Pending | P1 | Knowledge model; API/UI specs | Role scoped; audit events |
| PHASE 3 | Index | BM25/vector index + manifest lifecycle | Pending | P0 | Chunk spec; model/backend decisions | Rebuild/rollback reproducible |
| PHASE 3 | Retrieval | Fusion, filters, reranking, benchmark | Pending | P0 | Index; ACL model; decisions | Gold metrics meet approved thresholds; no leakage |
| PHASE 4 | RAG | Local LLM grounded answer orchestration | Pending | P0 | Retrieval; Ollama/model decision | Insufficient evidence and warning behavior |
| PHASE 4 | Citations | Server-side citation validation and viewer link | Pending | P0 | Page spans; RAG | All citations resolve to authorized evidence/page |
| PHASE 5 | Web app | Search/chat and evidence UX | Pending | P1 | API/RAG | Main query flow and warnings work |
| PHASE 5 | Admin UI | Ingestion review, KB and index screens | Pending | P1 | Phase 1/2 APIs | Authorized admin flow end-to-end |
| PHASE 6 | Security | Auth, RBAC, audit, hardening | Pending | P0 | Security decisions; APIs | Access matrix verified; no bypass |
| PHASE 7 | Quality | Automated/manual and RAG evaluation | Pending | P0 | Features complete; gold set | Release gates documented and met |
| PHASE 8 | Operations | Compose, backup/restore, offline runbook | Pending | P0 | Deployment decisions | Repeatable deployment and restore drill |

**Trạng thái:** Done / In Progress / Pending / Blocked. **Ưu tiên:** P0 release-critical, P1 important, P2 later. Task tiếp theo là PHASE 1 Ingestion engine; chưa bắt đầu trong lần này.
