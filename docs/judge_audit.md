# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (backend REPLAY: verdict của judge lưu sẵn trong CSV). FAIL là lớp dương — judge có nhiệm vụ *tìm* reply lỗi.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **Đạt** (cả 3) | **dùng** |
| helpful | 100 | 0.375 | 1.000 | **0.300** | **Không đạt** (κ < 0.6, R < 0.7) | **loại** |

Ma trận nhầm lẫn (FAIL = dương):

| | Judge FAIL | Judge PASS |
|---|---|---|
| **tone** — người FAIL | tp 24 | fn 6 |
| **tone** — người PASS | fp 4 | tn 66 |
| **helpful** — người FAIL | tp 9 | fn **21** |
| **helpful** — người PASS | fp 0 | tn 70 |

Tỉ lệ lỗi (Rogan-Gladen): tone quan sát 0.28 → hiệu chỉnh 0.30; helpful quan sát **0.09 → hiệu chỉnh 0.30**: judge helpful chỉ thấy 1/3 số reply lỗi thật.

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú → sửa rubric |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | **Người** | Xưng "em" + "nha" suồng sã với khách khiếu nại. Rubric: bắt buộc xưng "LogiX"/"anh/chị"; "em…nha", "bạn ơi" = FAIL. (H-017 cùng lỗi) |
| 2 | tone H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | **Người** | Judge bị đánh lừa bởi "Dạ, vui lòng". Rubric: chấm cả câu; câu mệnh lệnh / ngăn khách liên hệ = FAIL dù có từ lịch sự. |
| 3 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | **Người** | Judge phạt vì thiếu xin lỗi. Rubric: xin lỗi **không bắt buộc**; ngắn mà đủ ý, lịch sự = PASS. |
| 4 | tone H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | **Người** | CS LogiX cho phép từ "refund". Rubric: thêm danh sách thuật ngữ tiếng Anh được phép. |
| 5 | tone H-070 "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | **Người** | Rubric: emoji trong phản hồi khiếu nại = FAIL. |
| 6 | tone H-094 "Da, LogiX da hoan 40.000đ… xin loi…" | PASS | FAIL | **Người** | Tiếng Việt mất dấu (dịch máy). Rubric: không dấu / sai chính tả hàng loạt = FAIL. |
| 7 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** | Ghi chú: nhãn người sai (đọc nhầm ticket). Hành động: sửa nhãn ở phiên bản tập nhãn kế tiếp (không sửa CSV public đang dùng làm số tham chiếu của test); 1 nhãn người sai cho thấy cần người thứ hai chấm lại (double-label) các case bất đồng. |
| 8 | tone H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | **Người** | Đây là lỗi **nội dung** (hứa ngoài kết quả hệ thống), không phải giọng văn → không thuộc tiêu chí tone. Hành động: tách khỏi rubric tone, chấm bằng code (reply chỉ được nói điều ledger ghi — FM-08). |
| 9 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | **Người** | Judge không thấy ledger nên không biết số tiền sai. **18/21 case bỏ sót** là kiểu này (HL-015, HL-016, 020, 028, 035, 041, 043, 053, 058, 062, 070, 072, 074, 087, 090, 096, 098, 100). Hành động: tiền **không** chấm bằng judge → grader code so số trong reply với ledger (metric FM-08 ở M3). |
| 10 | helpful HL-016 / HL-028 (xin lỗi lặp 2–3 lần, câu dài) | PASS | FAIL | **Người** | Judge thiên vị câu dài, nhiều lời xin lỗi (verbosity bias). Rubric: lặp ý / lặp câu = FAIL; độ dài không phải điểm cộng. |
| 11 | helpful HL-047 / HL-091 / HL-097 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | **Người** | Không nói số tiền, không nói kết quả cụ thể. Rubric helpful phải có checklist: nêu kết quả (hoàn/không hoàn), **số tiền**, mã đơn, thời gian tiền về. |

## Kết luận
- **tone_ok dùng được** làm tiêu chí phụ: κ = 0.757, P = 0.857, R = 0.8 đều vượt sàn. 8/10 bất đồng người đúng → sửa rubric theo các dòng 1–6, 8; 1 case (H-081) nhãn người sai.
- **helpful bị loại, không được dùng làm gate**: ma trận nhầm lẫn cho fn = 21, tp = 9 → **recall 0.3** (bỏ sót 70% reply lỗi) và κ = 0.375 < 0.6. Precision 1.0 là ảo: judge gần như luôn nói PASS (91/100), nên ít khi nói FAIL sai. Dùng làm gate thì 21/30 reply lỗi lọt qua. Nguyên nhân chính: judge **không có ledger** → không kiểm được số tiền (18/21), cộng thiên vị câu dài.
- Hành động: phần "nói đúng số tiền" chuyển sang **grader code** (FM-08, M3); rubric helpful viết lại thành checklist rồi calibrate lại trên tập mới trước khi dùng.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng/tiêu chí); cần nhãn người mới (held-out, chấm đôi) để có đánh giá thật; κ/P/R trên 100 mẫu còn sai số lớn.
