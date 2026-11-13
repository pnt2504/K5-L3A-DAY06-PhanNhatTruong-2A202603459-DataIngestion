# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Pipeline của bài nộp dùng PostgreSQL + pgvector và multilingual E5 local. Làm theo [hướng dẫn chạy](starter/README.md) để lấy PDF, cài môi trường và tạo lại kết quả. Corpus có 39 trang được chọn trong [manifest](data/manifest.json). Bộ [benchmark](benchmark/README.md) gồm 15 câu dev và 5 câu test.

## Hồ sơ bài nộp

| Nội dung | Đường dẫn |
|---|---|
| Thông tin học viên | [STUDENT.md](STUDENT.md) |
| Cách tải dữ liệu, cài đặt và chạy | [starter/README.md](starter/README.md) |
| Mã pipeline | [starter/src/](starter/src/) |
| Manifest và quyền sử dụng dữ liệu | [data/manifest.json](data/manifest.json) |
| Câu hỏi, split và bằng chứng | [benchmark/questions.jsonl](benchmark/questions.jsonl) |
| Cấu hình, giả thuyết và kết quả A/B/C | [artifacts/experiment_log.csv](artifacts/experiment_log.csv) |
| Kết quả và log | [Tổng hợp](results/summary.json), [trace dev](results/dev_traces.jsonl), [trace test](results/test_traces.jsonl), [audit](results/manual_audit.json), [log ingest](results/ingestion.log) |
| Báo cáo cá nhân | [2A202603459_PhanNhatTruong.md](report/individual/2A202603459_PhanNhatTruong.md) |

## Nguồn và quyền sử dụng

- **MED001, MED002, MED004** lấy từ các hồ sơ CDC Stacks có nhãn Public Domain. MED002 chỉ được kiểm kê và đóng góp 0 trang vào corpus. [Kháng sinh](https://stacks.cdc.gov/view/cdc/60690) · [Răng miệng](https://stacks.cdc.gov/view/cdc/120015) · [Tiểu đường](https://stacks.cdc.gov/view/cdc/55517)
- **MED003** là *Hỏi đáp về phòng chống tác hại của rượu bia*, © World Health Organization 2019, WHO Regional Office for the Western Pacific, ISBN 9789290618874. Các đoạn trích MED003 trong benchmark, trace và demo được trích từ PDF, chuẩn hóa Unicode và khoảng trắng, rồi cắt theo ranh giới chunk khi áp dụng. Các đoạn trích và bản chuyển thể từ MED003 được chia sẻ cho mục đích phi thương mại theo cùng giấy phép **CC BY-NC-SA 3.0 IGO**. [Ấn phẩm WHO](https://www.who.int/vietnam/vi/health-topics/publications/9789290618836) · [Giấy phép](https://creativecommons.org/licenses/by-nc-sa/3.0/igo/)

Dùng manifest để lấy bản PDF tiếng Việt và đối chiếu SHA-256 trước khi tái tạo kết quả. Dùng số trang vật lý trong PDF khi kiểm tra bằng chứng.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
