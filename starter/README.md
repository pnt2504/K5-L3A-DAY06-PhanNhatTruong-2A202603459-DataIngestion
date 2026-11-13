# Chạy pipeline Day 06

Dùng Python 3.11, Docker Compose, PostgreSQL 16 và pgvector. Các lệnh PowerShell sau bắt đầu ở thư mục gốc repo.

## Chuẩn bị dữ liệu

Tải các PDF tiếng Việt có `counted_pages > 0` từ URL trong [manifest](../data/manifest.json) và lưu đúng tên file dưới đây, tính từ thư mục gốc repo. Nếu liên kết trực tiếp lỗi, mở trang ấn phẩm để tải bản tiếng Việt.

| Nguồn | Đường dẫn local | Trang ấn phẩm |
|---|---|---|
| MED001 | `data/Kháng sinh.pdf` | [CDC Stacks](https://stacks.cdc.gov/view/cdc/60690) |
| MED003 | `data/rượu bia.pdf` | [WHO Việt Nam](https://www.who.int/vietnam/vi/health-topics/publications/9789290618836) |
| MED004 | `data/tiểu đường.pdf` | [CDC Stacks](https://stacks.cdc.gov/view/cdc/55517) |

Pipeline kiểm tra SHA-256 của cả ba file. Cẩm nang răng miệng MED002 đóng góp 0 trang nên có thể bỏ qua khi tái tạo kết quả. Nếu gặp lỗi SHA-256, đối chiếu ngôn ngữ, phiên bản và checksum trong manifest trước khi chạy lại.

## Cài và chạy

```powershell
# Tạo môi trường nếu chưa có
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.11 -m venv .venv }
Set-Location starter
$python = '..\.venv\Scripts\python.exe'
& $python -X utf8 -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -p day6_student_starter up -d --wait
& $python scripts/check_setup.py
if (-not (Test-Path models/multilingual-e5-small/model.safetensors)) { & $python -X utf8 download_model.py }
& $python -X utf8 -m src.run
```

PostgreSQL nghe ở `127.0.0.1:55433`. Nếu đổi cổng, sửa cả `docker-compose.yml` và `DATABASE_URL` trong `.env`. Model chạy trên CPU và cần mạng ở bước tải lần đầu. Kết quả mặc định nằm tại `results/` ở gốc repo. Có thể chạy lại vào thư mục khác với `-m src.run --output ../results-rerun`.

## Cấu hình

| Cấu hình | Chunking | Truy xuất |
|---|---|---|
| A | 1.200 ký tự, overlap 200, trong phạm vi một trang | Cosine chính xác |
| B | Tối đa 1.200 ký tự, ưu tiên ngắt ở đoạn hoặc cuối câu, trong phạm vi một trang | Cosine chính xác |
| C | Dùng chung snapshot và vector với B | Cosine chính xác, áp dụng filter `topic` nếu câu hỏi cung cấp |

E5 dùng tiền tố `passage: ` và `query: ` cùng vector chuẩn hóa 384 chiều. Mỗi lần nạp thay snapshot của A hoặc B trong một transaction để bỏ chunk cũ. Pipeline nạp lại và đối chiếu toàn bộ ID trong database.

`selection.json` ghi cấu hình chọn từ dev trước khi truy xuất test. `dev_traces.jsonl`, `test_traces.jsonl` và `summary.json` chứa kết quả tự động. `coherence_samples.jsonl` và `test_audit_template.jsonl` là đầu vào để rà lại các nhãn trong `manual_audit.json`.

## Thử chatbot local

Sau khi pipeline đã nạp snapshot B, chạy lệnh dưới đây từ thư mục `starter/`.

```powershell
& ..\.venv\Scripts\python.exe -X utf8 -m src.chat
```

Mở [chatbot Day 06](http://127.0.0.1:8766/), nhập câu hỏi hoặc bấm một câu gợi ý. Chatbot truy xuất top-3 qua pgvector và trích câu liên quan bằng E5. Mỗi lượt tra cứu độc lập. Chọn một chủ đề để áp dụng filter trước khi xếp hạng, rồi bấm vào nguồn để xem toàn bộ chunk. Chatbot chạy local bằng model đã tải, không cần API key.
