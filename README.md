# Day 04 Lab v2 — Research Agent Tool Eval

## Tổng quan

Trong lab này, nhóm sẽ xây dựng một research agent nhỏ nhưng chạy thật. Agent sẽ:

- nhận yêu cầu từ người dùng;
- chọn tool phù hợp;
- truyền arguments đúng;
- chạy tool thật;
- lưu toàn bộ log JSON;
- dùng log đó để tối ưu prompt và tool declaration qua nhiều version.

> Mục tiêu học tập không phải là “chatbot trả lời hay”, mà là xây dựng một vòng lặp evidence-driven và có thể đo lường được.

## Mục tiêu học tập

1. Chạy baseline bằng API thật.
2. Đọc run JSON để phát hiện lỗi về tool, arguments, missing follow-up hoặc gọi tool thừa.
3. Cập nhật prompt hoặc tool declaration trong các file phù hợp.
4. Chạy lại và ghi versioning.
5. Tự viết eval case để đo những lỗi nhóm quan tâm.
6. Viết report dựa trên dữ liệu thật, không dựa vào cảm giác.

## Phạm vi công việc

### Yêu cầu bắt buộc

- Setup chạy được bằng provider thật.
- Agent có ít nhất 5 tool trong [starter_v0/artifacts/tools.yaml](starter_v0/artifacts/tools.yaml).
- Chạy base eval.
- Tối ưu ít nhất 3 vòng sau baseline: v1, v2, v3.
- Ghi lại lịch sử version vào [starter_v0/artifacts/version_log.csv](starter_v0/artifacts/version_log.csv).
- Viết thêm ít nhất 1 tool mới kèm theo tài liệu và đăng ký đúng các file cần thiết.
- Tự viết đúng 10 eval case vào [starter_v0/data/eval_group.json](starter_v0/data/eval_group.json): 5 single-turn + 5 multi-turn.
- Nộp run JSON, transcript JSON và report.
- Có UI chạy được. Streamlit là khuyến nghị nhanh nhất, nhưng nhóm có thể dùng framework khác.
- Hoàn thành [starter_v0/artifacts/REPORT.md](starter_v0/artifacts/REPORT.md): phần A trước deadline demo, phần B hoàn thiện sau.

### Tools mở rộng (không tính là tool mới của team)

- send: gửi text lên Telegram; live-send là optional.
- policy, papers, paper_text: tải/trích PDF; đều optional.

### Điểm bonus

Điểm bonus dành cho nhóm hoàn thành UI bắt buộc và tự viết thêm hơn 3 tool mới. UI riêng lẻ hoặc các optional tool có sẵn không được tính là bonus.

## Bằng chứng tối thiểu trên UI

UI tốt không chỉ là “có chat”. Mỗi demo nên hiển thị:

- request và response cuối cùng;
- trace từng tool: tên tool, args, round/status, result/error;
- transcript, run và artifact version để biết đang xem version nào;
- cùng một scenario được chạy qua nhiều prompt/tool version để thấy cải thiện rõ ràng.

Nếu dùng Streamlit, cần:

- thêm `streamlit>=1.30.0` vào requirements;
- tạo `app.py` tái sử dụng `run_model_tool_loop` trong `chat.py`;
- hiển thị `rounds/tool_events` và lưu transcript;
- chạy `streamlit run app.py` và kiểm tra tại `http://localhost:8501`.

## Deploy để team khác test

UI chạy local chỉ đủ cho máy của nhóm build. Nếu team khác cần test từ máy khác thì phải có URL truy cập được.

Cách nhanh nhất cho link tạm là Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://localhost:8501
```

Lấy URL `trycloudflare.com` được tạo ra, paste vào report phần A, rồi test lại bằng browser hoặc thiết bị khác trước buổi demo.

> Chỉ dùng tunnel tạm thời và đừng để lộ secrets hoặc dữ liệu nhạy cảm trong UI public.

## Thiết kế tool cũng là một phần của prompt engineering

Không chỉ prompt quyết định kết quả. Tên tool và mô tả tool cũng là một phần của interface với model.

### Nguyên tắc ưu tiên

- tên tool phản ánh đúng intent;
- mô tả nói rõ khi nào dùng / khi nào không dùng;
- mô tả nêu convention cho arguments và default quan trọng;
- action tool phải nêu rõ confirmation boundary.

### Khi đổi tên tool

Phải đồng bộ các file sau:

1. [starter_v0/artifacts/system_prompt.md](starter_v0/artifacts/system_prompt.md)
2. [starter_v0/artifacts/tools.yaml](starter_v0/artifacts/tools.yaml)
3. [starter_v0/tools/tool_name/TOOL.md](starter_v0/tools)
4. [starter_v0/tools/__init__.py](starter_v0/tools/__init__.py)
5. [starter_v0/data/eval_base.json](starter_v0/data/eval_base.json)
6. [starter_v0/data/eval_research_extension.json](starter_v0/data/eval_research_extension.json)
7. [starter_v0/data/eval_group.json](starter_v0/data/eval_group.json) nếu case có nhắc đến tool đó
8. [starter_v0/artifacts/REPORT.md](starter_v0/artifacts/REPORT.md) và các text demo/poster

> Nếu không đồng bộ đủ, eval dễ báo lỗi như “not declared in tools.yaml” hoặc khiến model và grader nói hai thứ khác nhau.

## Các file quan trọng

| Path                                                                                | Mục đích                                |
| ----------------------------------------------------------------------------------- | ------------------------------------------ |
| [starter_v0/artifacts/system_prompt.md](starter_v0/artifacts/system_prompt.md)       | instruction cho agent                      |
| [starter_v0/artifacts/tools.yaml](starter_v0/artifacts/tools.yaml)                   | tên, mô tả và schema của tool         |
| [starter_v0/artifacts/version_log.csv](starter_v0/artifacts/version_log.csv)         | giả thuyết và metric theo version       |
| [starter_v0/artifacts/REPORT.md](starter_v0/artifacts/REPORT.md)                     | tài liệu demo và bằng chứng nộp bài |
| [starter_v0/data/eval_base.json](starter_v0/data/eval_base.json)                     | base eval cố định                       |
| [starter_v0/data/eval_group.json](starter_v0/data/eval_group.json)                   | 10 case do nhóm tự viết                 |
| [starter_v0/tools](starter_v0/tools)                                                 | thư mục tool mới và implementation     |
| [starter_v0/scripts/preflight_provider.py](starter_v0/scripts/preflight_provider.py) | kiểm tra provider                         |

## Tool tracks

Phần này chỉ tóm tắt mỗi tool làm gì. Việc quyết định khi nào dùng tool nào là phần nhóm tự định nghĩa trong prompt và tool declaration.

### Core tools

- clarify: hỏi lại người dùng khi thiếu thông tin hoặc cần xác nhận yes/no trước hành động nhạy cảm.
- timeline: lấy bài đăng gần đây của một tài khoản.
- social_search: tìm bài đăng theo từ khóa.
- lookup: tìm trên web.
- fetch: đọc nội dung một URL.
- format: trình bày các item đã có thành markdown digest.

### Optional/advanced tools

- send: gửi text lên Telegram channel.
- policy: tìm trong company policy markdown nội bộ.
- papers: tìm paper trên arXiv.
- paper_text: tải PDF arXiv và trích text cục bộ.

## Setup

Xem chi tiết về key, smoke test và lưu ý Windows trong [TOOL-SETUP.md](TOOL-SETUP.md).

### Tóm tắt nhanh

```bash
cd starter_v0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Mở `.env`, điền ít nhất key của model provider rồi lưu file. Sau đó chạy:

```bash
python scripts/preflight_provider.py --provider openrouter
```

> Không ghi đè `.env` đã có. Nếu dùng provider khác, thay `openrouter` trong mọi command.

## Quy trình làm việc

### Bước 1 — Chạy baseline

Chạy fixed base eval với version v0:

```bash
python run_eval.py --provider openai --version v0 --suite base --eval-cases data/eval_base.json
```

Đọc các trường chính trong run JSON:

- `summary.case_accuracy`
- `summary.tool_routing_accuracy`
- `summary.argument_accuracy`
- `summary.multiturn_accuracy`
- `summary.provider_error_cases`
- `summary.measured_cases`
- `results[*].result.failures`
- `results[*].result.observed_mismatch`

### Điều kiện metric có giá trị

- `provider_error_cases` phải bằng `0`.
- `measured_cases` phải bằng `total_cases`.
- các `tool_results` có error cần review thủ công.

### Bước 2 — Sửa một thứ duy nhất

Trong từng vòng tối ưu routing, chỉ sửa:

- [starter_v0/artifacts/system_prompt.md](starter_v0/artifacts/system_prompt.md)
- [starter_v0/artifacts/tools.yaml](starter_v0/artifacts/tools.yaml)

Không sửa cases trong [starter_v0/data/eval_base.json](starter_v0/data/eval_base.json), ngoại trừ field tên tool trong trường hợp rename.

Phương pháp làm việc tốt:

1. Mở run JSON và đọc `observed_mismatch`, `failures`, `actual_tool_calls`, `tool_results`.
2. Đặt một giả thuyết về nguyên nhân sai.
3. Chỉ sửa đúng một thứ để kiểm chứng giả thuyết đó.
4. Chạy lại, so sánh metric trước/sau, rồi ghi version log.

### Bước 3 — Chạy 3 version tối ưu hóa

Không chạy ba lệnh liên tiếp như một thao tác copy-paste. Mỗi lần nên:

- đổi một hypothesis;
- chạy đúng một version;
- ghi lại evidence.

```bash
python run_eval.py --provider openrouter --version v1 --suite base --eval-cases data/eval_base.json
python run_eval.py --provider openrouter --version v2 --suite base --eval-cases data/eval_base.json
python run_eval.py --provider openrouter --version v3 --suite base --eval-cases data/eval_base.json
```

Sau mỗi run, điền vào [starter_v0/artifacts/version_log.csv](starter_v0/artifacts/version_log.csv):

```text
version,author,changed_artifact,artifact_version,prompt_hash,tools_hash,reason,hypothesis,metric_name,metric_before,metric_after,run_file
```

### Bước 4 — Thêm team eval

[starter_v0/data/eval_group.json](starter_v0/data/eval_group.json) phải có đúng 10 case:

- 5 single-turn dùng `query`
- 5 multi-turn dùng `turns`

Mỗi case cần có:

- `id`
- `phase`: luôn `"B"`
- `failure_type`: một trong `wrong_tool`, `wrong_arg_value`, `wrong_boundary`, `unnecessary_tool`, `out_of_scope`, `missing_info`
- `expect`: `tool_calls` hoặc `no_tool`
- `metadata.what_it_tests`

Chạy team eval:

```bash
python run_eval.py --provider openrouter --version v3 --suite group --eval-cases data/eval_group.json
```

Optional extension eval:

```bash
python run_eval.py --provider openrouter --version v3 --suite extension --eval-cases data/eval_research_extension.json
```

### Bước 5 — Chat live

```bash
python chat.py --provider openrouter --version v3
```

Nên thử ít nhất 3 live turn:

- một request research bình thường;
- một request thiếu thông tin rồi bổ sung ở lượt sau;
- một request có hành động nhạy cảm để kiểm tra boundary hỏi lại/xác nhận.

## Chuẩn bị demo

Trước demo, team nên rehearse 3–5 scenario cụ thể để showcase được tool đã làm gì và version nào cải thiện gì.

### Checklist tối thiểu

- khóa artifact trước buổi demo;
- kiểm tra API key, quota và link demo còn sống;
- mở sẵn logs, run JSON và transcript cần chiếu;
- chuẩn bị fallback run hoặc fallback transcript nếu mạng chập chờn;
- không để lộ secrets trong screenshot, log hoặc poster;
- cùng một scenario nên được so sánh xuyên suốt v0 → later versions để thấy cải thiện rõ.

## Hoàn thiện report

Hoàn thành [starter_v0/artifacts/REPORT.md](starter_v0/artifacts/REPORT.md). File này có 2 phần:

- Phần A — Giới thiệu agent: ngắn gọn, 1 trang, giúp người khác hiểu nhanh agent có tool gì và thử bằng câu hỏi nào.
- Phần B — Chi tiết / bằng chứng: bảng đầy đủ v0–v3, failure analysis, eval cases, live chat, reflection — dựa trên log thật.

## Nộp bài

Nộp thư mục [starter_v0](starter_v0) với:

- [starter_v0/artifacts/system_prompt.md](starter_v0/artifacts/system_prompt.md)
- [starter_v0/artifacts/tools.yaml](starter_v0/artifacts/tools.yaml)
- [starter_v0/artifacts/version_log.csv](starter_v0/artifacts/version_log.csv)
- [starter_v0/artifacts/REPORT.md](starter_v0/artifacts/REPORT.md)
- [starter_v0/data/eval_group.json](starter_v0/data/eval_group.json)
- runs JSON, analysis CSV nếu có, transcript JSON
- implementation của tool mới, code UI và dependency tương ứng

> Không nộp `.env`, API keys, `.venv/` hoặc cache/build output.

## Checkpoints — K3 buổi sáng (09:00–13:00)

0. Kickoff — 09:00–09:15: chia nhóm, phân vai và mở [starter_v0](starter_v0).
1. Setup — 09:15–09:40: chuẩn bị môi trường, API keys và chạy provider preflight.
2. Baseline v0 — 09:40–10:15: chạy base eval, đọc failed trace, dựng UI local và ghi bốn metric.
3. v1 + Tool — 10:15–10:50: sửa một giả thuyết, hoàn thiện một tool mới, chạy v1 và cập nhật version log.
4. Nghỉ — 10:50–11:05.
5. Eval + v2 — 11:05–11:30: hoàn thành 10 team eval cases, evidence v2, ba kịch bản demo, report A và rehearsal.
6. Demo → Ship — 11:30–12:40:
   - Showdown — 11:30–12:15: giới thiệu, live test và challenge.
   - v3 + Report B — 12:15–12:35: áp dụng feedback, chạy v3 và hoàn thiện report bằng evidence.
   - Final gate — 12:35–12:40: kiểm tra và chuẩn bị nộp [starter_v0](starter_v0).
7. Kahoot Recap — 12:40–13:00.
