# 08. Retrieval Specification

## 1. Thành phần bắt buộc
Vector search Qdrant; BM25/lexical search; filter theo metadata và ACL; hợp nhất kết quả; reranking; trace lưu được để giải thích. Backend BM25 và thuật toán fusion/reranker còn TBD.

## 2. Trình tự
1. Xác thực và dựng phạm vi quyền ở server.
2. Phân tích truy vấn: cụm chính xác (số hiệu/điều), intent, ngày áp dụng và filter tường minh; không tự áp filter suy diễn thành sự thật.
3. Chạy song song lexical/vector với cùng điều kiện ACL và trạng thái phát hành.
4. Hợp nhất danh sách; khử trùng theo chunk/node/version; rerank bằng model cục bộ.
5. Điều chỉnh theo hiệu lực/độ tin cậy chỉ sau relevance, không để điểm heuristic che nguồn xung đột.
6. Trả top evidence đa dạng, provenance và lý do loại/cảnh báo phù hợp.

## 3. Bộ lọc và chính sách
Document class, collection/ACL, cơ quan, loại, lĩnh vực, ngày ban hành, hiệu lực tại ngày hỏi, version/approval, page/node. Filter bắt buộc quyền không được nới bởi câu hỏi người dùng. Tài liệu hết hiệu lực có thể truy xuất khi người dùng hỏi lịch sử, nhưng phải gắn cảnh báo.

## 4. Hiệu lực và xung đột
Mặc định ưu tiên tài liệu xác minh còn hiệu lực ở ngày áp dụng. Giữ ứng viên sửa đổi/thay thế/bãi bỏ cạnh căn cứ gốc khi cần giải thích. Khi relation chưa xác minh hoặc nguồn bất đồng, gắn warning và tránh kết luận tuyệt đối.

## 5. Chỉ số và kiểm soát
Recall@k, MRR/nDCG, precision evidence, ACL leakage = 0, citation coverage, hiệu năng, lỗi lọc hiệu lực. Benchmark theo truy vấn pháp lý Việt Nam và tri thức nội bộ, phân tầng theo exact lookup, câu hỏi ngữ nghĩa, lịch sử, scan/OCR. Ngưỡng, k, trọng số và latency TBD.

## 6. Vận hành index
Manifest version hóa corpus snapshot, chunk set, embedding model, cấu hình vector, lexical analyzer và thời điểm build. Hỗ trợ trạng thái BUILDING/READY/ACTIVE/FAILED/RETIRED, kiểm tra count/hash, rollback và rebuild. Không tự xóa index cũ trước khi xác nhận chuyển đổi.
