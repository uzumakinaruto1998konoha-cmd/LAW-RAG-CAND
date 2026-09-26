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
