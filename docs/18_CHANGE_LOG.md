# 18. Change Log

## 2026-09-26 — Phase 0 initial specification
- Tạo bộ 18 tài liệu kế hoạch/đặc tả và `PROJECT_STATE.json` theo yêu cầu.
- Xác lập stack baseline đúng yêu cầu; ghi rõ đề xuất kiến trúc modular monolith + worker và các quyết định còn mở.
- Chưa tạo mã nguồn, chưa thêm framework/dịch vụ, chưa dùng API cloud.
- Rà soát chéo: requirement, dependency, conflict và TBD được ghi trong tài liệu tương ứng.

## 2026-09-26 — Phase 0 approval and Phase 1 ingestion design
- Ghi nhận project owner approval Phase 0 theo yêu cầu trong phiên; mở PHASE 1.
- Hoàn tất task thiết kế ingestion đầu tiên: định dạng/giới hạn v1, extraction/OCR local, filesystem storage, review threshold và corpus manifest.
- Cập nhật ADR-004..006, kiến trúc, testing spec, task board và project state. Chưa tạo code hay cài dependencies; task tiếp theo là ingestion engine.

## 2026-09-26 — Phase 1 ingestion engine
- Thêm lõi upload/validation/hash, filesystem content-addressed storage, exact dedup/idempotency, trạng thái/retry job, PostgreSQL DB-API adapter, migration và audit sink.
- Thêm unit tests cho định dạng, giới hạn, lỗi, storage/job lifecycle; 14 test đạt. Không cài dependency ngoài.
- Chốt ADR-003 dùng bảng PostgreSQL không broker; cập nhật kiến trúc, TASK_BOARD và PROJECT_STATE. Task tiếp theo: extraction/OCR.

## 2026-09-26 — Phase 1 extraction
- Thêm trích xuất PDF (page/text/bbox, mixed scan OCR), DOCX paragraph/table/source locator, UTF-8 text và JPG/PNG OCR; lưu confidence, tool versions, traineddata SHA-256, pipeline version và review warnings.
- Pin PyMuPDF 1.28.2, python-docx 1.2.0, Pillow 12.3.0; yêu cầu Tesseract 5.5.3 + `vie`. Project owner chấp thuận PyMuPDF AGPL v3 cho triển khai nội bộ. Không tải/cài package hay binary trong task.
- 26 unit tests và compile check đạt. Tesseract chưa có trên máy hiện tại; OCR được kiểm tra bằng adapter giả và đường thiếu-engine/review, cần chạy golden corpus OCR trong môi trường đã đóng gói binary/model.
- Cập nhật ADR-005, đặc tả ingestion, kiến trúc, deployment/testing spec, task board và project state. Task tiếp theo: legal parsing.

## 2026-09-27 — Phase 1 legal parsing
- Thêm rule-based legal parser (`legal_rules`, `legal_parsing`): ghép span thành dòng đọc, dựng cây CHAPTER/SECTION/ARTICLE/CLAUSE/POINT/APPENDIX, trích metadata và nhận diện ứng viên quan hệ; mọi giá trị có provenance (page/locator/detector), confidence, raw value và mã cảnh báo ổn định.
- Thêm workflow review (`legal_review`): quyết định accept/correct/reject theo metadata/node/relation, lưu reviewer và thời điểm, audit từng quyết định; chỉ duyệt khi không còn item pending và mọi warning đã được acknowledge.
- Thêm adapter PostgreSQL và `migrations/0002_legal_parsing.sql` (legal_parse_run, legal_node, metadata_assertion, document_relation_candidate, review_decision, document_approval); không thêm driver.
- Thêm 29 unit tests (parse từ DOCX thật, cây node, metadata, quan hệ, review gate, adapter); 55 test toàn repo đạt. Không thêm dependency, không nhúng nội dung luật vào source.
- Cập nhật ADR-006, docs/05, docs/06, docs/13, task board và project state. Task tiếp theo: release to KB (approval, dedup, version, processing run).

## 2026-09-27 — Phase 1 release to knowledge base
- Thêm `migrations/0003_release_to_kb.sql`: schema cho document identity (unique document_number + issuing_body + document_type), document_version (immutable snapshot với version_number, dates, content_hash), document_relation (verified relations), processing_run (release/index operations tracking), version_processing_record (audit trail), và duplicate_candidate (near-duplicate detection).
- Thêm domain models `kb_models.py`: Document, DocumentVersion, DocumentRelation, ProcessingRun, VersionProcessingRecord, DuplicateCandidate với validation logic và temporal properties.
- Thêm PostgreSQL adapter `kb_postgres.py`: KnowledgeBaseRepository với CRUD operations cho tất cả KB entities, support document versioning và duplicate tracking.
- Thêm service layer `kb_release.py`: ReleaseService orchestrate approved documents sang retrievable KB, tạo/update document identity, increment version numbers, compute content hash cho deduplication, track processing runs, và transition job status sang INDEXING.
- Thêm ReleaseError vào `errors.py`.
- Thêm 18 unit tests `test_kb_models.py` cho domain model validation; 73 tests toàn repo đạt. Không thêm dependency.
- Design: Document identity enforced bởi unique constraint; versions không tự động supersede (admin quản lý); content-based dedup qua SHA-256 của nodes+metadata; chỉ approved documents được release; processing runs có manifest và error tracking.
- Cập nhật task board và project state. Task tiếp theo: PHASE 2 knowledge model hoặc tiếp tục PHASE 1 corpus testing.

## 2026-09-27 — Phase 2 knowledge model and ACL
- Thêm `migrations/0004_knowledge_model_acl.sql`: RBAC schema với app_user, role, permission, user_role, role_permission; document collections cho ACL scoping (document_collection, collection_access, document_collection_member); session management (user_session, password_reset_token); validity_status field cho document_version.
- Default roles theo docs/10: system_admin, knowledge_admin, reviewer, user, auditor với permissions matrix.
- Default permissions: document operations (upload/view/view_restricted/edit_metadata/approve/delete), version/relation/user/role/audit/index/collection management.
- Thêm domain models `knowledge_models.py`: AppUser, Role, Permission, UserRole, DocumentCollection, CollectionAccess, UserSession, PasswordResetToken, ValidityStatus enum, AccessLevel enum.
- Thêm service layer `authorization.py`: AuthorizationService với permission checks, collection/document access validation, và AuditLogger cho access audit trail.
- Thêm 27 unit tests `test_knowledge_model.py` cho RBAC/ACL/temporal features; 100 tests toàn repo đạt. Không thêm dependency.
- Design: RBAC với role-based permissions; collection-based ACL cho document access; temporal role assignments với expiry; validity status tracking cho effective dates; session management với expiry/revocation.
- Cập nhật task board và project state. Task tiếp theo: Knowledge UI/API implementation hoặc PHASE 3 Index.

## 2026-09-27 — Phase 3 index infrastructure and chunking
- Thêm `migrations/0005_index_retrieval.sql`: Schema cho chunking (chunk_set, chunk với structural path preservation), index manifests (index_manifest, chunk_index_record), retrieval traces (retrieval_trace, retrieval_result), và search metrics.
- Thêm domain models `retrieval/models.py`: ChunkSet, Chunk, IndexManifest, RetrievalTrace, RetrievalResult với enums IndexType/IndexStatus/QueryType/RetrievalMethod.
- Thêm service `retrieval/chunking.py`: ChunkingService generate chunks từ legal nodes ở article/clause/point level, preserve structural path (Chương/Mục/Điều), maintain page spans và provenance.
- Chunk strategy theo docs/07: legal boundaries ưu tiên hơn token length; chunk ở cấp Điều khi phù hợp; giữ structural path, heading, page locations.
- Index manifest versioning: support BUILDING/READY/ACTIVE/FAILED/RETIRED states; track embedding model, lexical analyzer, chunk/document counts; reproducible builds.
- Retrieval traces: audit trail cho mọi search query với user_id, query type, filters, as_of_date, result count, latency.
- Thêm 16 unit tests `test_retrieval.py` cho chunking/indexing models; 116 tests toàn repo đạt. Không thêm dependency.
- Design: Legal-aware chunking với boundary preservation; manifest lifecycle cho index versioning; retrieval audit trail; chuẩn bị cho hybrid search (BM25 + vector).
- Cập nhật task board và project state. Task tiếp theo: PHASE 3 retrieval implementation (hybrid search, fusion, ACL filtering) hoặc PHASE 4 RAG.

## 2026-09-27 — Phase 4 RAG and citations
- Thêm `migrations/0006_rag_citations.sql`: Schema cho conversations (conversation, message), evidence tracking (evidence, citation, message_warning), và RAG metrics.
- Thêm domain models `rag/models.py`: Conversation, Message, Evidence, Citation, RAGResponse với enums MessageRole/CitationStatus.
- Thêm service `rag/service.py`: RAGService cho grounded answer generation, insufficient evidence detection, server-side citation generation.
- RAG pipeline per docs/04: Evidence → Context → LLM (Ollama) → Grounded answer → Citation validation → Response.
- Insufficient evidence handling: Clear indication when no evidence found, warnings about unverified/invalid documents.
- Citation generation: Server-side only from evidence IDs (no hallucinated citations per docs/04 section 4).
- Conversation management: Track conversation threads, message history, and retrieval traces.
- Warning system: Document unverified status, validity status, missing as_of_date.
- Thêm 15 unit tests `test_rag.py` cho RAG models and service; 131 tests toàn repo đạt. Không thêm dependency.
- Design: Grounded answer generation với explicit evidence citations; separation of "what document says" vs "interpretation"; ACL filtering at retrieval layer.
- Cập nhật task board và project state. Task tiếp theo: Complete PHASE 3 retrieval hoặc PHASE 5 UI development.
