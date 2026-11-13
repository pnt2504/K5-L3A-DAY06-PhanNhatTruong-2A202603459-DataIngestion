# Báo cáo cá nhân Day 06

## Dữ liệu và pipeline

Corpus gồm 39 trang nội dung từ ba PDF tiếng Việt về kháng sinh, tác hại của rượu bia và tự quản lý bệnh tiểu đường. [Manifest](../../data/manifest.json) ghi nguồn, giấy phép, checksum, danh sách trang và quy tắc chọn. Cẩm nang răng miệng được kiểm kê với 0 trang đóng góp vào corpus.

Pipeline dùng pypdf 6.21.4, chuẩn hóa NFC, gom khoảng trắng trong đoạn và giữ dấu ngắt đoạn. Số trang là số trang PDF vật lý tính từ 1. Hai trang đầu PDF rượu bia không có text trích được và nằm ngoài corpus. Các bảng có thể mất cấu trúc hàng cột khi trích text. Log đọc tài liệu nằm trong [results](../../results/ingestion.log).

Model `intfloat/multilingual-e5-small` chạy CPU với Sentence Transformers 6.3.0 và Torch 2.15.0, sinh vector chuẩn hóa 384 chiều. Văn bản và câu hỏi lần lượt có tiền tố `passage: ` và `query: `. PostgreSQL 16.16, pgvector 0.8.7 và psycopg 3.3.8 lưu vector và tìm cosine chính xác. Chi phí dịch vụ bên ngoài là 0 USD. [Lệnh tái lập](../../starter/README.md)

Mỗi chunk giữ ID tài liệu, đường dẫn nguồn, số trang, page ID, ngôn ngữ, chủ đề và khoảng ký tự trên text chuẩn hóa. `topic` lấy từ manifest và dùng để giới hạn phạm vi truy xuất khi câu hỏi cung cấp phạm vi. Đây là nhãn cấp tài liệu nên độ phân giải của filter phụ thuộc vào cách chia chủ đề của corpus.

## Cấu hình và benchmark

A dùng cửa sổ 1.200 ký tự, overlap 200. B ưu tiên ngắt ở đoạn hoặc cuối câu, giới hạn 1.200 ký tự. C dùng chung chunk và vector với B, thêm filter `topic` khi có. Hai snapshot A và B đều được nạp lại và kiểm tra giữ nguyên toàn bộ ID.

Bộ câu hỏi được cố định trước khi chạy, gồm 15 dev, 5 test và 4 câu có filter, trong đó 2 câu test. Mọi đoạn evidence được kiểm tra trong trang nguồn. Hai tập dùng chung tài liệu và các trang gold khác nhau. Tiêu chí chọn ưu tiên Evidence Hit@3 trên dev, tiếp đến Hit@1, số chunk và thứ tự A–B–C khi hòa. B được chọn trước khi chạy test. [Bộ câu hỏi và quy tắc chấm](../../benchmark/README.md) · [Quyết định trên dev](../../results/selection.json)

## Kết quả

| Cấu hình | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 | Chunk | Tổng token passage | Chi phí |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 11/15 | 13/15 | 4/5 | 5/5 | 69 | 17.228 | 0 USD |
| B | 12/15 | 13/15 | 4/5 | 5/5 | 69 | 15.623 | 0 USD |
| C | 12/15 | 13/15 | 4/5 | 5/5 | 69 | Dùng chung với B | 0 USD |

A có độ dài trung bình 941 ký tự, B và C là 854 ký tự. Thời gian ingest đo trên máy local và phân bố độ dài chi tiết nằm trong [summary.json](../../results/summary.json). C dùng trực tiếp snapshot B nên thời gian ingest riêng để trống.

| Cấu hình | Coherence /2 (n) | Metadata đủ và đúng | Top-3 đúng phạm vi trên câu test có filter | Grounding 0/1/2 và trung bình /2 |
|---|---:|---:|---:|---:|
| A | 1,7 (10) | 15/15 | 2/2 | 0/0/5 · 2,0 |
| B | 1,9 (10) | 15/15 | 2/2 | 0/0/5 · 2,0 |
| C | 1,9 (10) | 15/15 | 2/2 | 0/0/5 · 2,0 |

A và B truy xuất không lọc. Chỉ C áp dụng filter trên hai câu test có phạm vi. Coherence được chấm tại cùng 10 vị trí nguồn. Metadata của 45 chunk test được đối chiếu với manifest và text trích lại từ PDF. Codex hỗ trợ triển khai, chạy và đề xuất nhãn coherence và grounding từ các mẫu đã lưu. Ngày 13/11/2026, Phan Nhật Trường xác nhận đồng ý giữ nguyên các nhãn audit. [Mẫu coherence](../../results/coherence_samples.jsonl) · [Nhãn và lý do](../../results/manual_audit.json)

## Phân tích

- A–B. B đưa bằng chứng của `q06` về chi phí vô hình ở MED003 trang 16 từ hạng 3 lên hạng 1. Trong mẫu coherence, A cắt ngang câu ở `q01` và `q10`, còn B kết thúc tại ranh giới câu. B dùng khoảng 9,3% ít token passage hơn A nhờ bỏ overlap và ưu tiên ngắt theo nội dung.
- B–C. B và C trả cùng thứ tự top-3 trên cả bốn câu có filter. Các kết quả của B vốn đã cùng chủ đề yêu cầu. Filter giúp giới hạn phạm vi bằng SQL, còn bộ câu hỏi hiện tại chưa đo được lợi ích về thứ hạng. Phạm vi của mỗi topic cũng trùng với một tài liệu trong corpus.
- `q11` trượt top-3 ở cả ba cấu hình. Câu hỏi cần tỷ lệ các nhóm thức ăn ở MED004 trang 11, nhưng top-3 trả các trang 12, 10 và 3. Các đoạn liên quan đến chăm sóc chung hoặc kế hoạch bữa ăn chưa đủ để trả lời tỷ lệ.
- `q14` lấy được chunk từ đúng MED003 trang 36 ở hạng 2, nhưng chunk đó bàn về các quy định và thiếu danh sách thư điện tử, tin nhắn và podcasting. Trường hợp này cho thấy chỉ khớp trang sẽ đếm dư hit.
- `q20` có bằng chứng về định nghĩa huyết áp ở MED004 trang 8 tại hạng 2. Cả ba cấu hình ưu tiên trang 7, nơi có nhắc huyết áp trong mục ABC. Câu này trượt Hit@1 nhưng đạt Evidence Hit@3 và grounding 2.

Kết quả 5 câu test chỉ mô tả bộ câu hỏi này. Có thể mở rộng bộ đánh giá bằng nhiều tài liệu cùng chủ đề và câu hỏi có các đoạn dễ nhầm giữa các phạm vi, để đo giá trị riêng của filter.
