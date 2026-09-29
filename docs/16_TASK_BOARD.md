# 16. Task Board

| Phase | Epic | Task | Status | Priority | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|---|
| PHASE 0 | Baseline | Tạo bộ đặc tả ban đầu | Done | P0 | — | 18 tài liệu + state; liên kết yêu cầu/kiến trúc |
| PHASE 0 | Review | Rà soát consistency, conflict, dependency | Done | P0 | Baseline | Findings được ghi; không code |
| PHASE 0 | Decisions | Chốt TBD và phê duyệt baseline | Done | P0 | Review | Project owner xác nhận Phase 0 baseline được chấp thuận trong phiên 2026-09-26; TBD chưa thuộc ingestion vẫn tiếp tục theo Decision Log |
| PHASE 1 | Ingestion design | Chốt formats, giới hạn, OCR/parser và lưu trữ | Done | P0 | Phase 0 approval | Lựa chọn ingestion v1, ngưỡng review và corpus manifest được ghi ở docs/05, ADR-004..006, docs/13 |
| PHASE 1 | Ingestion engine | Upload, hash, validation, job lifecycle | Done | P0 | Ingestion design | Exact duplicate/idempotency; signature/size validation; immutable blob; PostgreSQL job state + audit; safe errors; 14 unit tests pass |
| PHASE 1 | Extraction | PDF/DOCX/text/image extraction và OCR | Done | P0 | Ingestion engine; OCR decision | Page/bbox mapping; OCR confidence/version/traineddata hash; <90/no text/missing engine → review; 26 unit tests pass |
| PHASE 1 | Legal parsing | Metadata + hierarchy + relation candidates | Done | P0 | Extraction; legal schema | Node/provenance/confidence; reviewer workflow; 29 unit tests pass |
| PHASE 1 | Release to KB | Approval, dedup, version and processing run | Done | P0 | Legal parsing; schema | Schema 0003; document identity unique constraint; versioning increment; content hash dedup; processing run tracking; 18 unit tests pass |
| PHASE 2 | Knowledge model | Implement document/legal schema and ACL | Done | P0 | Phase 1 design; decisions | RBAC with 5 default roles, 14 permissions; collection-based ACL; validity_status tracking; 27 unit tests pass |
| PHASE 2 | Knowledge UI/API | Manage document, metadata, version, relation | Pending | P1 | Knowledge model; API/UI specs | Role scoped; audit events. Read API (documents/versions/chunks) đã có trong PHASE 5; ghi/duyệt/UI còn lại |
| PHASE 3 | Index | BM25/vector index + manifest lifecycle | Done | P0 | Chunk spec; model/backend decisions | Chunk generation với legal boundary preservation; index manifest với versioning; 16 unit tests pass |
| PHASE 3 | Retrieval | Fusion, filters, reranking, benchmark | Done | P0 | Index; ACL model; decisions | Hybrid search (BM25 + vector), RRF/weighted fusion, zero ACL leakage, temporal validity check, legal reranker, retrieval trace; 12 unit tests pass |
| PHASE 4 | RAG | Local LLM grounded answer orchestration | Done | P0 | Retrieval; Ollama/model decision | Grounded answer generation, insufficient evidence detection, conversation management; 15 unit tests pass |
| PHASE 4 | Citations | Server-side citation validation and viewer link | Done | P0 | Page spans; RAG | Server-generated citations from evidence IDs, validation, viewer URL; integration with RAG response |
| PHASE 5 | API backend | FastAPI `/api/v1` endpoints + server-side authn/authz | Done | P1 | RAG; citations; ACL model | Chat/search/documents/conversations/upload/jobs/traces/health/review/approve trên `/api/v1`; phân trang limit/offset; bearer token; RBAC deny-by-default + ACL collection; 404 không lộ ACL; error envelope chuẩn; OpenAPI là contract; 220 tests pass |
| PHASE 5 | Web app | Search/chat and evidence UX | Done | P1 | API/RAG | Search/chat + evidence UX, hội thoại (kết nối GET /conversations), kho tài liệu (list/detail), trace, admin upload/job, health/readiness; SPA tĩnh mount qua FastAPI; tsc -b + vite build, ESLint và 38 test Vitest đạt |
| PHASE 5 | Admin UI | Ingestion review, KB and index screens | Done | P1 | Phase 1/2 APIs | Upload + job status + tổng quan KB theo quyền; API review/approve/retry sẵn sàng; bootstrap config mẫu và script run_app.py khởi chạy trọn vẹn |
| PHASE 6 | Security | Auth, RBAC, audit, hardening | In Progress | P0 | Security decisions; APIs | Access matrix verified; SHA-256 token hash; audit events ghi nhận toàn bộ vòng đời văn bản |
| PHASE 7 | Quality | Automated/manual and RAG evaluation | Pending | P0 | Features complete; gold set | Release gates documented and met |
| PHASE 8 | Operations | Compose, backup/restore, offline runbook | Pending | P0 | Deployment decisions | Repeatable deployment and restore drill; script scripts/run_app.py và run_dev.ps1 sẵn sàng |

**Trạng thái:** Done / In Progress / Pending / Blocked. **Ưu tiên:** P0 release-critical, P1 important, P2 later. Task tiếp theo: chạy benchmark corpus đã duyệt (PHASE 7), hoặc bổ sung Dockerfile / docker-compose cho triển khai vận hành offline (PHASE 8).

