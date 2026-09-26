# 09. Citation Specification

## 1. Mục tiêu
Mỗi citation phải trỏ tới evidence nội bộ cụ thể, duyệt được, đúng phiên bản và quyền; hiển thị định danh pháp lý cùng nguồn và vị trí vật lý.

## 2. Trường citation
`citation_id`, `document_id`, `document_version_id`, tên/số hiệu/cơ quan, node path (Chương/Mục/Điều/Khoản/Điểm), excerpt, page start/end, source span/bounding box nếu có, URL nội bộ mở viewer, trạng thái hiệu lực tại ngày hỏi, source type, verification state.

## 3. Quy tắc sinh
Server sinh citation từ evidence IDs, không nhận citation tự do của LLM. Mọi căn cứ pháp lý phải có ít nhất một citation. Excerpt giữ nguyên chữ nguồn (có thể hiển thị ellipsis do UI); nội dung diễn giải phải phân biệt rõ. Không bịa số trang/node; nếu không có locator đủ tin cậy phải báo không có vị trí chính xác.

## 4. Kiểm tra
Trước trả lời, xác nhận ID thuộc retrieval trace, user có quyền, version còn tồn tại, nội dung span khớp, metadata/node/page hợp lệ và ngày hiệu lực được tính cùng `as_of_date`. Citation lỗi bị loại và câu trả lời phải được cập nhật/đánh dấu thiếu căn cứ.

## 5. PDF viewer
Mở đúng file version và trang 1-based. Tọa độ highlight tùy khả năng extraction; page link vẫn bắt buộc khi có PDF. Không hứa định vị chính xác vùng nếu PDF scan/OCR không lưu bounding box.

## 6. Hiển thị
Hiển thị tên nguồn, số/ký hiệu, trạng thái hiệu lực/ngày tra cứu, cấu trúc pháp lý và trang; cảnh báo tài liệu nội bộ hoặc OCR confidence thấp. Tránh citation chỉ là URL mơ hồ.
