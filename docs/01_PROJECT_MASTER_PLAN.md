# 01. Project Master Plan — LAW-RAG-CAND

## 1. Mục đích
Xây dựng hệ thống chatbot tra cứu pháp luật, nghiệp vụ và tri thức nội bộ, có thể vận hành trong mạng LAN/offline. Câu trả lời phải dựa trên tài liệu được phân quyền và truy xuất, có dẫn chiếu kiểm chứng được; hệ thống phải quản lý được cấu trúc, hiệu lực, phiên bản và quan hệ văn bản.

## 2. Phạm vi Phase 0
Phase 0 chỉ lập và rà soát đặc tả. Không triển khai mã nguồn, không kết nối dịch vụ cloud, không thay đổi stack. Bộ tài liệu chuẩn gồm 18 Markdown này cùng `PROJECT_STATE.json`.

## 3. Nguyên tắc
- Nguồn nội bộ là căn cứ trả lời; không suy diễn thành căn cứ pháp luật.
- Lưu bản gốc bất biến, ghi nhận nguồn gốc, phiên bản xử lý và dấu vết thao tác.
- Phân biệt dữ liệu chưa xác minh với dữ liệu đã được người có thẩm quyền duyệt.
- Ưu tiên văn bản còn hiệu lực theo ngày tra cứu, nhưng không xóa lịch sử.
- Tôn trọng phân quyền ngay từ truy xuất, không chỉ ở giao diện.
- Mọi thông tin chưa được quyết định phải được ghi là TBD, không tự chọn âm thầm.

## 4. Sản phẩm và kiến trúc mục tiêu
Backend Python/FastAPI; giao diện React + TypeScript; PostgreSQL cho dữ liệu quan hệ và quyền; Qdrant cho vector; Ollama cho mô hình chạy cục bộ; Docker Compose cho triển khai. Ingestion hỗ trợ PDF/DOCX/ảnh/văn bản và OCR scan. Tìm kiếm kết hợp lexical BM25, vector, bộ lọc metadata và reranking. Xem `03_SYSTEM_ARCHITECTURE.md`.

## 5. Các giai đoạn
PHASE 0 đặc tả; PHASE 1 Document Ingestion Engine; PHASE 2 Knowledge Base; PHASE 3 Hybrid Retrieval; PHASE 4 RAG + LLM; PHASE 5 Web Application; PHASE 6 Security; PHASE 7 Testing; PHASE 8 Deployment. Chi tiết và cổng nghiệm thu nằm trong `15_ROADMAP.md`.

## 6. Tiêu chí hoàn thành toàn dự án
- Ingest được các định dạng đã yêu cầu, OCR scan, lưu trang/vị trí và trạng thái duyệt.
- Phân tích được cấu trúc pháp luật và metadata; phát hiện trùng, quản lý phiên bản, hiệu lực và quan hệ.
- Chunk theo cấu trúc pháp luật; hybrid retrieval có lọc quyền, metadata và reranking.
- Trả lời có dẫn chiếu truy ngược tới điều/khoản/điểm, tài liệu và trang; có cơ chế từ chối khi thiếu chứng cứ.
- RBAC, audit, quản trị tài liệu/index, backup/restore được kiểm chứng.
- Cài đặt và vận hành LAN/offline theo runbook; không cần API cloud.

## 7. Quản trị thay đổi
Mọi thay đổi phạm vi/kiến trúc phải ghi lý do, tác động, người quyết định và ngày trong `17_DECISION_LOG.md`; cập nhật đồng bộ đặc tả, state và changelog. Chưa có phê duyệt thay đổi kiến trúc ở Phase 0.

## 8. Trạng thái hiện tại
Phase 0 — bộ đặc tả ban đầu. Task tiếp theo: chủ dự án quyết định các mục TBD trong Decision Log, sau đó khóa baseline Phase 0 và bắt đầu đặc tả/thiết kế chi tiết cho task đầu tiên Phase 1.
