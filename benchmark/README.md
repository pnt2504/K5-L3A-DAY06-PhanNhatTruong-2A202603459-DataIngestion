# Benchmark Day 06

`questions.jsonl` chứa 20 câu hỏi từ các trang được chọn trong `data/manifest.json`. Mỗi dòng là một đối tượng JSON. `gold_source_id` trỏ tới `source_id` trong manifest. `gold_page` dùng số trang PDF vật lý, bắt đầu từ 1. `evidence_quote` là đoạn trích sau chuẩn hóa Unicode NFC và gộp khoảng trắng.

## Chia tập và áp dụng filter

- Dev gồm `q01`–`q15`. Test gồm `q16`–`q20`. Hai tập dùng chung tài liệu nhưng dùng các trang gold khác nhau. Kết quả test phản ánh truy xuất trên các câu hỏi và trang gold chưa dùng để chỉnh cấu hình trong cùng corpus.
- Bốn câu có filter `topic` gồm `q03`, `q10`, `q16` và `q19`. Giá trị `topic` đến từ phạm vi nêu trong câu hỏi và dùng các giá trị đã khai báo trong manifest. Chỉ cấu hình C áp dụng filter này trước khi xếp hạng. C chạy trên toàn corpus với các câu thiếu trường `filter`.
- Dùng cùng câu hỏi cho A, B và C. Khi truy xuất, truyền trường `question` và filter nếu cấu hình hỗ trợ. Dùng các trường gold và đáp án ở bước chấm.

## Tiêu chí chọn và đánh giá

1. Chạy A, B, C trên dev. Chọn theo Evidence Hit@3 cao nhất, sau đó Hit@1 cao nhất, sau đó số chunk ít nhất. Nếu vẫn hòa, ưu tiên cấu hình đơn giản hơn theo thứ tự A, B, C. Ghi cấu hình đã chốt trước khi mở kết quả test.
2. Chạy các cấu hình đã cố định trên test. Báo riêng Hit@1 và Evidence Hit@3 dạng `n/N` cho từng tập và cấu hình. Một hit cần đúng nguồn và trang, đồng thời một chunk phải chứa đủ đoạn bằng chứng hoặc bằng chứng tương đương đã được người chấm xác nhận.
3. Chấm coherence trên cùng 10 vị trí nguồn cho A, B và C. Dùng vị trí bắt đầu lần xuất hiện đầu tiên của `evidence_quote` trên trang gold của `q01`–`q10`. Khi nhiều chunk chứa cùng vị trí, chọn chunk bắt đầu sớm nhất trên trang. Chấm từ 0 đến 2 và ghi lý do theo `GUIDE.md`.
4. Với 5 câu test mỗi cấu hình, kiểm tra metadata của các chunk trả về, ghi mức tuân thủ filter của các câu có filter và chấm grounding từ 0 đến 2 theo độ đủ của bằng chứng trong top-3. Lưu các nhãn và lý do cùng trace. So sánh A–B và B–C theo chất lượng và tài nguyên.
