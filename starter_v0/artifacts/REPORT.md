# Day 04 Lab v2 Report — Research Agent Tool Eval

## Thành viên nhóm

| STT | Họ và tên | MSSV |
|---:|---|---|
| 1 | Nguyễn Văn Đạt | 2A202601969 |
| 2 | Nguyễn Trọng Toàn | 2A202601493 |
| 3 | Hoàng Nguyễn Phong | 2A202601077 |
| 6 | Nguyễn Kim Trung Đức | 2A202601325 |
| 7 | Nguyễn Việt Thắng | 2A202601321 |
| 9 | Lê Hồng Đức | 2A202601313 |
| 11 | Kim Duy Hưng | 2A202501763 |

## Thông tin report

- Team: DAY04_G18_E403
- Provider/model dùng cho bản evidence chính: `openrouter` / `openai/gpt-4o-mini`
- UI local: chạy `streamlit run app.py`, mở `http://localhost:8501`
- Public demo URL: chưa cấu hình Cloudflare Tunnel trong log hiện có

---

# PHẦN A — Giới Thiệu Agent

## A1. Agent này làm được gì

Agent là một research assistant nhỏ có khả năng chọn tool phù hợp, truyền đúng arguments, chạy tool thật và lưu lại đầy đủ JSON log/transcript để phục vụ đánh giá. Agent hỗ trợ tìm tin web, tìm/xem nội dung mạng xã hội, đọc URL, định dạng digest, hỏi lại khi thiếu thông tin, xác nhận trước hành động nhạy cảm và tra cứu thời tiết bằng tool mới của nhóm.

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi lại người dùng khi thiếu thông tin hoặc cần xác nhận `yes_no` trước hành động nhạy cảm. | Không |
| `timeline` | Lấy bài đăng gần đây của một tài khoản mạng xã hội theo `screenname`. | Không |
| `social_search` | Tìm bài đăng mạng xã hội theo từ khóa, hỗ trợ `Latest` hoặc `Top`. | Không |
| `lookup` | Tra cứu thông tin trên web, phân biệt `general` và `news`, có `timeframe`. | Không |
| `fetch` | Đọc nội dung từ một URL cụ thể. | Không |
| `format` | Trình bày các item đã có thành markdown digest theo template. | Không |
| `send` | Gửi text lên Telegram, chỉ nên chạy sau khi đã được xác nhận. | Optional built-in |
| `policy` | Tìm trong tài liệu chính sách nội bộ. | Optional built-in |
| `papers` | Tìm bài báo khoa học trên arXiv. | Optional built-in |
| `paper_text` | Tải/trích text từ paper arXiv. | Optional built-in |
| `weather` | Lấy thời tiết hiện tại theo thành phố qua OpenWeather API. | Có |

## A3. Câu hỏi mẫu để thử

1. `Thời tiết Hà Nội hôm nay thế nào?`
2. `Cho mình xem thời tiết Tokyo tính bằng độ F.`
3. `Tweet mới nhất của Sam Altman là gì?`
4. `Tìm tin tức AI trong tuần này trên web và Twitter.`
5. `Gửi bản tin AI mới nhất lên Telegram giúp mình.`

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| Hỏi thời tiết Hà Nội | `weather(city="Hanoi")` | Tool mới `weather` mở rộng năng lực ngoài bộ core. | `transcripts/v0_openai_20260729T111652716131.transcript.json` |
| Request thiếu thông tin: “Xem dự báo thời tiết giúp mình với.” | `clarify(response_type="text")` | Sau v2/v3, agent biết hỏi lại thay vì tự đoán thành phố. | `runs/v10_B_group_openrouter_20260729T112709694112.json` |
| Gửi Telegram | `clarify(response_type="yes_no")` trước `send` | v0 gọi `send` trực tiếp; v3 đặt boundary xác nhận đúng. | `runs/v3_B_base_openrouter_20260729T104214496762.json` |
| Tìm tin AI trên web và mạng xã hội | `lookup(topic="news")` + `social_search(query="AI")` | v3 sửa mô tả tool để giữ đúng args và không mất `topic`. | `runs/v3_B_base_openrouter_20260729T104214496762.json` |

---

# PHẦN B — Chi Tiết / Bằng Chứng

Điều kiện metric hợp lệ đều đạt: `provider_error_cases = 0`, `measured_cases = total_cases`. Bản evidence chính dùng run JSON trong `runs/` và versioning trong `artifacts/version_log.csv`.

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Case Acc | Routing Acc | Arg Acc | Multiturn Acc | Run File |
|---|---|---|---:|---:|---:|---:|---|
| v0 | Baseline | Đánh giá hiện trạng prompt/tool declaration ban đầu. | 0.70 | 0.75 | 0.70 | 1.00 | `runs/v0_B_base_openrouter_20260729T095944198171.json` |
| v1 | Sửa `system_prompt.md` | Cấm bịa dữ liệu và từ chối tool ngoài lề sẽ giảm lỗi out-of-scope. | 0.80 | 0.85 | 0.80 | 0.8333 | `runs/v1_B_base_openrouter_20260729T101644720178.json` |
| v2 | Bổ sung strict rules cho `clarify` | Ép dùng `clarify` đúng boundary sẽ pass các case thiếu thông tin/xác nhận. | 0.75 | 0.95 | 0.75 | 0.8333 | `runs/v2_B_base_openrouter_20260729T103153126748.json` |
| v3 | Sửa `tools.yaml`, bắt buộc và mô tả rõ `response_type` | Tool schema/mô tả rõ hơn sẽ sửa lỗi args của `clarify` và `lookup`. | 1.00 | 1.00 | 1.00 | 1.00 | `runs/v3_B_base_openrouter_20260729T104214496762.json` |

Group eval cũng đạt 10/10:

| Suite | Provider | Total | Measured | Provider Errors | Case Acc | Run File |
|---|---|---:|---:|---:|---:|---|
| group | openrouter | 10 | 10 | 0 | 1.00 | `runs/v10_B_group_openrouter_20260729T112709694112.json` |
| group | openai | 10 | 10 | 0 | 1.00 | `runs/v2_B_group_openai_20260729T114248739983.json` |

## B2. Failure analysis

| Case ID | Version | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|---|
| R08_out_of_scope | v0 | out_of_scope | `send` | Agent gọi tool cho yêu cầu không thuộc phạm vi research. | v1 thêm quy tắc từ chối/tool-free cho out-of-scope. |
| R10_missing_handle | v0 | missing_info | `timeline` | Thiếu handle nhưng agent vẫn gọi timeline. | v2 ép dùng `clarify` khi thiếu thông tin. |
| R11_missing_url | v0 | missing_info | `fetch` | Thiếu URL nhưng agent vẫn gọi fetch. | v2 ép hỏi lại bằng `clarify(response_type="text")`. |
| R12_confirm_before_send | v0/v1/v2 | wrong_boundary | `send` hoặc `clarify` sai args | Hành động gửi Telegram cần xác nhận `yes_no`; v2 vẫn truyền `text`. | v3 sửa schema/mô tả `tools.yaml` cho `response_type`. |
| R13_parallel_web_and_tweets | v0/v2 | wrong_arg_value | `lookup`, `social_search` | `lookup` thiếu `topic="news"` hoặc query bị lệch. | v3 làm rõ convention args trong tool declaration. |
| M02_carryover_timeframe | v2 | wrong_arg_value | `social_search` | Multi-turn cần chuyển sang `lookup` nhưng chọn sai tool. | v3 mô tả rõ boundary giữa web lookup và social search. |
| M06_switch_tool | v1 | wrong_tool | `lookup`, `social_search` | Agent gọi thừa `social_search` khi chỉ cần tool mới theo lượt hiện tại. | v3 nhấn mạnh không gọi tool thừa và dùng ngữ cảnh lượt cuối. |

## B3. Team eval cases

`data/eval_group.json` có đúng 10 case: 5 single-turn và 5 multi-turn. Kết quả group eval: 10/10 pass.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_weather_routing | Tra cứu thời tiết Hà Nội. | `weather(city="Hanoi")` | Pass |
| G02_weather_imperial | Thời tiết với đơn vị Fahrenheit. | `weather(city="Tokyo", units="imperial")` | Pass |
| G03_policy_data_privacy | Tra cứu policy bảo mật dữ liệu. | `policy(policy_area="data_privacy")` | Pass |
| G04_arxiv_paper_search | Tìm paper về LLM. | `papers(query="Large Language Models")` | Pass |
| G05_out_of_scope_math | Toán đơn giản không cần tool. | `no_tool` | Pass |
| G06_multiturn_clarify_weather | Thiếu tên thành phố. | `clarify(response_type="text")` | Pass |
| G07_multiturn_clarify_telegram | Xác nhận trước Telegram. | `clarify(response_type="yes_no")` | Pass |
| G08_multiturn_search_then_fetch | Lượt sau yêu cầu đọc URL. | `fetch(url=...)` | Pass |
| G09_multiturn_correction_city | Người dùng sửa thành phố. | `weather(city="Da Nang")` | Pass |
| G10_multiturn_carryover_topic | Giữ chủ đề GPT-4o, đổi kênh sang Twitter. | `social_search(query="GPT-4o")` | Pass |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| Thời tiết Hà Nội | v0/openai | `weather(city="Hanoi")` | `transcripts/v0_openai_20260729T111652716131.transcript.json` | Trả về nhiệt độ, cảm giác như, độ ẩm, mô tả thời tiết và gió. |
| Thời tiết Tokyo | v0/openai | `weather(city="Tokyo")` | `transcripts/v0_openai_20260729T111652716131.transcript.json` | Tool mới chạy thật và có result từ OpenWeather. |
| Người dùng hỏi thiếu thông tin về bài báo | v0/openai | `clarify(response_type="text")` | `transcripts/v0_openai_20260729T113211176860.transcript.json` | Agent chờ người dùng bổ sung thay vì tự đoán. |
| Tìm tweet theo keyword | v0/openai | `social_search(query="model mythos site:twitter.com/anthropic", search_type="Latest")` | `transcripts/v0_openai_20260729T101655681351.transcript.json` | Agent gọi social search và trả lời dựa trên kết quả rỗng. |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên | `tools/weather/TOOL.md`, `tools/weather/tool.py`, `artifacts/tools.yaml` | `weather` nhận `city`, `units`, gọi OpenWeather API và trả dữ liệu có cấu trúc. | Cần `OPENWEATHER_API_KEY`; nếu thiếu key trả lỗi `missing_api_key` rõ ràng. |
| Core routing tools | `runs/v3_B_base_openrouter_20260729T104214496762.json` | Base eval đạt 20/20: routing, args và multiturn đều 1.00. | Cần tiếp tục review thủ công tool result nếu API bên ngoài lỗi. |
| Optional built-in | `data/eval_group.json`, `runs/v10_B_group_openrouter_20260729T112709694112.json` | `policy`, `papers`, `fetch`, `social_search` được kiểm thử trong group eval. | Optional tools có thể ảnh hưởng routing nếu mô tả quá rộng. |
| UI core deliverable | `app.py`, `requirements.txt` | Streamlit app có thể chạy bằng `streamlit run app.py`; dependency có `streamlit>=1.30.0`. | Cần public URL nếu team khác test từ máy khác. |

## B6. Reflection

- Những lỗi về hành vi tổng quát nên sửa trong `system_prompt.md`: không bịa dữ liệu, không gọi tool ngoài phạm vi, hỏi lại khi thiếu thông tin, không tự ý thực hiện hành động nhạy cảm.
- Những lỗi về routing/argument nên sửa trong `tools.yaml`: tên tool, mô tả khi nào dùng, default args, enum và đặc biệt `clarify.response_type`.
- Case cần review thủ công: các tool gọi API thật như `weather`, `lookup`, `fetch`, `papers`; routing pass chưa đảm bảo API trả dữ liệu tốt.
- Cải tiến tiếp theo: bổ sung public demo URL, thêm transcript v3 riêng cho ba scenario demo chính, và tách rõ optional tools nếu muốn giảm nhiễu routing.
