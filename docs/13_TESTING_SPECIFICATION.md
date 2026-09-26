# 13. Testing Specification

## 1. Chiến lược
Thiết kế kiểm thử theo requirement và rủi ro, thực hiện từ unit tới tích hợp, end-to-end, bảo mật, retrieval/RAG evaluation, backup/restore và nghiệm thu người dùng. Không đặt ngưỡng chưa được duyệt.

## 2. Nhóm kiểm thử
- Ingestion: từng format, text PDF/scan/mixed, OCR tiếng Việt, trang xoay, DOCX, ảnh, file lỗi/trùng.
- Parser: hierarchy đúng/sai, numbering ngoại lệ, bảng/phụ lục, confidence và review.
- Legal model: versioning, ngày hiệu lực, quan hệ, partial repeal/amendment, lịch sử as-of.
- Chunk/retrieval: boundary, hybrid recall, exact number lookup, filter, ACL non-leakage, rerank và index rollback.
- RAG/citation: groundedness, citation span/page, đủ/thiếu evidence, xung đột, hiệu lực lịch sử, chống bịa nguồn.
- API/UI: RBAC, workflow review, viewer page, lỗi/partial state, audit.
- Security/operations: upload abuse, injection, authz bypass, secret scan, backup integrity, restore drill, offline/LAN.

## 3. Dữ liệu đánh giá
Tập kiểm thử có tài liệu chuẩn hóa/đã cấp quyền, truy vấn, evidence gold, answer rubric và expected warnings; chuyên gia pháp chế xác nhận. Dữ liệu nhạy cảm phải được xử lý theo chính sách chưa chốt.

Corpus cho ingestion v1 được định nghĩa bằng manifest ở `docs/05_DOCUMENT_INGESTION_SPECIFICATION.md`, bao gồm PDF text/scan/mixed, OCR tiếng Việt thẳng/xoay/mờ, DOCX nhiều trang, JPG/PNG, UTF-8, file hỏng, MIME giả, vượt giới hạn và exact duplicate. Mỗi fixture cần hash, nhãn expected page/text/metadata/hierarchy/review, quyền sử dụng và người duyệt; không đưa nội dung luật tự tạo vào source code.

## 4. Tiêu chí release
Traceability requirement-to-test; không có lỗi blocker về ACL leakage, citation bịa, mất dữ liệu hoặc restore; ngưỡng chất lượng/hiệu năng và người ký duyệt TBD. Không coi LLM judge là bằng chứng duy nhất.

## 5. Báo cáo
Ghi build/config/model/index versions, dữ liệu, metrics, lỗi đã biết và quyết định chấp nhận rủi ro. Môi trường test phải đại diện cấu hình offline dự kiến.
