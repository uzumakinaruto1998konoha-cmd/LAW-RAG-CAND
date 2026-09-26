# 02. Requirements

## 1. Quy ước
ID requirement ổn định; MUST là bắt buộc, SHOULD là khuyến nghị trong phạm vi kiến trúc đã nêu, TBD là cần chủ dự án quyết định. Chưa gán các ngưỡng hiệu năng/SLA khi chưa có dữ liệu tải.

## 2. Chức năng
| ID | Requirement | Ưu tiên |
|---|---|---|
| FR-001 | Quản trị viên nạp PDF, DOCX, PDF scan, JPG/PNG và tài liệu văn bản. | MUST |
| FR-002 | Phát hiện nội dung scan/thiếu text và OCR; giữ liên hệ trang/vùng nguồn. | MUST |
| FR-003 | Trích xuất, chuẩn hóa text; giữ bản gốc và kết quả xử lý có phiên bản. | MUST |
| FR-004 | Nhận diện Chương, Mục, Điều, Khoản, Điểm; cho phép sửa/duyệt kết quả. | MUST |
| FR-005 | Trích xuất metadata văn bản; ghi nhận độ tin cậy và nguồn trích xuất. | MUST |
| FR-006 | Phát hiện tài liệu/bản tải lên trùng; hỗ trợ quản lý phiên bản. | MUST |
| FR-007 | Quản lý số/ký hiệu, cơ quan, ngày ban hành, ngày hiệu lực, ngày hết hiệu lực và trạng thái hiệu lực theo thời điểm. | MUST |
| FR-008 | Quản lý quan hệ sửa đổi, bổ sung, thay thế, bãi bỏ, hướng dẫn, dẫn chiếu; giữ provenance. | MUST |
| FR-009 | Chunking bảo toàn cấu trúc pháp luật, nguồn trang và quy tắc riêng; không chỉ chia theo token. | MUST |
| FR-010 | Tìm kiếm hybrid: vector, BM25, metadata filtering, reranking. | MUST |
| FR-011 | Chat dựa trên nguồn truy xuất được phép; không tự tạo căn cứ/số văn bản; nêu rõ thiếu căn cứ. | MUST |
| FR-012 | Trích dẫn Điều/Khoản/Điểm, nguồn tài liệu và mở đúng trang PDF khi có định vị. | MUST |
| FR-013 | Ưu tiên văn bản còn hiệu lực; cảnh báo hiệu lực/xung đột, không tự kết luận khi dữ liệu chưa xác minh. | MUST |
| FR-014 | RBAC, quản lý người dùng, audit log, quản lý tài liệu và index. | MUST |
| FR-015 | Có quy trình backup và restore được kiểm chứng. | MUST |
| FR-016 | Cung cấp giao diện web React + TypeScript và API FastAPI. | MUST |
| FR-017 | Vận hành LAN/offline với Ollama; không gọi cloud API nếu chưa được cho phép. | MUST |

## 3. Phi chức năng
- NFR-001: Stack giới hạn ở Python/FastAPI, React/TypeScript, PostgreSQL, Qdrant, Ollama, Docker Compose; bổ sung thư viện phụ trợ chỉ sau quyết định ghi log.
- NFR-002: Mọi đường truy xuất phải áp dụng quyền trước khi nội dung được đưa vào prompt hoặc hiển thị.
- NFR-003: Có thể tái tạo index từ dữ liệu chuẩn và cấu hình đã lưu; phiên bản pipeline/index phải nhận diện được.
- NFR-004: Hệ thống ghi audit cho hành động quản trị và sự kiện truy cập quan trọng; nội dung cần ghi và thời hạn lưu TBD.
- NFR-005: Hạn chế خروج dữ liệu; vận hành lõi không cần Internet. Cập nhật model/phần mềm offline qua quy trình TBD.
- NFR-006: Ngưỡng tải, độ trễ, dung lượng, RPO/RTO, tính sẵn sàng và thời hạn lưu TBD.

## 4. Ngoài phạm vi đã xác nhận
Tự đồng bộ nguồn luật bên ngoài; tư vấn pháp lý thay chuyên gia; ký số; tích hợp SSO/IdP; triển khai cloud; đa tenant; ngưỡng SLA cụ thể. Các mục này không được xem là đã loại vĩnh viễn, cần quyết định riêng nếu phát sinh.

## 5. Tiêu chí nghiệp vụ xuyên suốt
Mỗi phát biểu pháp lý trong câu trả lời phải truy về đoạn nguồn và phiên bản tài liệu cụ thể. Không dùng trạng thái hiệu lực suy đoán như dữ kiện chắc chắn. Tài liệu nội bộ và tài liệu pháp luật có nhãn/phân loại nguồn riêng.
