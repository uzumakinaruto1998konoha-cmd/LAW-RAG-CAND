# 07. Chunking Specification

## 1. Nguyên tắc
Ranh giới pháp lý ưu tiên hơn độ dài token. Không tách một đơn vị Điều/Khoản/Điểm nếu còn phù hợp; token chỉ là giới hạn kỹ thuật, không là tiêu chí duy nhất. Chunk phải giữ đường dẫn cấu trúc, nguyên văn, trang và version.

## 2. Phân cấp
Document version → Chương → Mục → Điều → Khoản → Điểm → đoạn/vế. Parser tạo cây node; nội dung không nhận diện được giữ thành node/segment UNKNOWN có vị trí, chờ review.

## 3. Quy tắc tạo chunk
- Chunk chuẩn ở cấp Điều khi kích thước phù hợp; có tiêu đề và ngữ cảnh Chương/Mục.
- Điều dài: chia theo Khoản; Khoản dài chia theo Điểm/đoạn, luôn kèm đường dẫn và tiêu đề Điều.
- Đơn vị ngắn liền kề có thể gộp có giới hạn, nhưng không gộp qua Điều/nguồn khác nếu làm mờ citation.
- Điểm/khoản phụ thuộc câu dẫn: lặp câu dẫn cần thiết trong context, đánh dấu phần lặp; bản trích dẫn vẫn trỏ đúng span nguyên văn.
- Bảng/phụ lục/định nghĩa/biểu mẫu được xử lý riêng theo cấu trúc và page span.
- Văn bản nội bộ áp dụng cấu trúc heading/đoạn, gắn loại nguồn, không ép vào hierarchy pháp luật.

## 4. Kích thước và overlap
Target/max tokens, tokenizer, overlap và quy tắc cắt đoạn TBD sau benchmark model tiếng Việt. Overlap chỉ dùng trong một đơn vị cấu trúc khi cần và phải chống trùng citation; không overlap mù qua điều khoản.

## 5. Metadata chunk bắt buộc
chunk_id ổn định trong chunk set; document/version; node/path; loại nguồn; nội dung; page start/end và spans; hash; ngày hiệu lực/validity; trạng thái xác minh; ACL; parser/chunker version; embedding model/index version.

## 6. Phiên bản hóa
Thay đổi nội dung hoặc thuật toán tạo ChunkSet mới; manifest ghi parser/chunker/tokenizer/embedding versions. Reindex không làm mất index đang phục vụ cho tới khi swap nguyên tử hoặc quy trình chuyển đổi được xác định.

## 7. Chất lượng
Đánh giá boundary accuracy, citation span accuracy, retrieval recall theo Điều/Khoản, duplicate rate, coverage trang và kích thước. Mẫu kiểm tra do chuyên gia duyệt; ngưỡng TBD.
