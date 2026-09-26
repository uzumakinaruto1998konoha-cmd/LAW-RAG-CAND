# 04. Legal RAG Specification

## 1. Mục tiêu
Trả lời tra cứu có căn cứ, tái kiểm chứng được theo nguồn, vị trí, phiên bản và thời điểm hiệu lực. RAG hỗ trợ tìm kiếm, không thay thế phê duyệt nghiệp vụ hay tư vấn chuyên môn.

## 2. Chuẩn evidence
Mỗi evidence item gồm document/version ID, loại nguồn, số/ký hiệu nếu có, trạng thái duyệt, cấu trúc pháp lý, text nguyên văn đã chuẩn hóa, trang/vị trí, hiệu lực theo ngày tra cứu, quyền truy cập và điểm retrieval. Chỉ dùng evidence đã được duyệt và được phép truy cập; chính sách với tri thức chưa duyệt TBD.

## 3. Pipeline trả lời
1. Nhận diện intent và ngày cần áp dụng (mặc định ngày hiện tại theo timezone cấu hình; timezone mặc định TBD).
2. Áp dụng ACL, loại nguồn, cơ quan/lĩnh vực/thời gian và trạng thái.
3. Hybrid retrieve, hợp nhất, rerank, xử lý quan hệ sửa đổi/thay thế/bãi bỏ.
4. Tạo context có nhãn nguồn và cấu trúc; yêu cầu mô hình chỉ tổng hợp trong giới hạn evidence.
5. Kiểm tra citation, hiệu lực, quyền và mức hỗ trợ; loại citation không tồn tại hoặc không khớp.
6. Trả câu trả lời, căn cứ, nguồn/trang, cảnh báo và giới hạn.

## 4. Kiểm soát hallucination
Không cho phép model tự điền số văn bản/citation. Citation được dựng từ ID evidence phía server. Mệnh đề không được evidence hỗ trợ phải bỏ hoặc ghi rõ chưa đủ căn cứ. Tách “văn bản nói gì” khỏi “áp dụng vào tình huống” và yêu cầu cảnh báo khi thiếu dữ kiện. Không có kết luận hiệu lực tự động nếu quan hệ pháp lý chưa xác minh.

## 5. Xung đột và hiệu lực
Xây dựng timeline theo ngày hiệu lực và quan hệ đã xác minh; hiển thị văn bản sửa đổi và điều khoản liên quan. Khi nguồn xung đột, dữ liệu hiệu lực thiếu, hoặc có nhiều cách hiểu, trình bày cảnh báo và các nguồn tương ứng, không tự phân xử vượt dữ liệu. Quy tắc chọn văn bản ưu tiên theo thứ bậc pháp lý và nguồn ngoài kho hiện chưa được đặc tả.

## 6. Đầu ra API logic
`answer`, `evidence[]`, `citations[]`, `warnings[]`, `as_of_date`, `insufficient_evidence`, `trace_id`. Schema chi tiết ở `11_API_SPECIFICATION.md`.

## 7. Đánh giá
Đo recall evidence, độ chính xác citation, groundedness, từ chối đúng, lỗi hiệu lực, ACL leakage, chất lượng tiếng Việt và độ trễ. Ngưỡng nghiệm thu TBD; bộ dữ liệu chuẩn cần chuyên gia pháp chế duyệt.
