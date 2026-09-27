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
