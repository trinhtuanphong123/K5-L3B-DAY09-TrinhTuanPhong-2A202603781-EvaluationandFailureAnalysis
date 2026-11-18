# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: `seeded_regression C-002@11` — tin ticket hơn DB (FM-03)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, report `E-seeded_regression-20261118-30f3` (eval set `30f33e0918da`), row `E-002@11` |
| Triệu chứng | Lab 8 grader FAIL (`status resolved != denied`); `db_fact_kept` fail ("1 override event(s)"), `refund_amount_correct` fail ("ledger 20000 != label 0"), `proposal_amount_correct` fail. **Ledger ghi 20000** (refund_count 1) trong khi nhãn là 0 / `denied`. Reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." **khớp ledger** → `reply_amount_matches_ledger` pass: reply không nói dối, khoản hoàn mới là thứ sai. |
| Bước sai đầu tiên | **ev 3 `model_override` `{"delay_days": 5}`** |
| Vì sao là bước *đầu tiên* | ev 1 `handoff` đúng (`claim_id` C-002, tool được phép `lookup_order/lookup_policy/compute_compensation`). ev 2 `investigator` đọc DB đúng: đơn O-202 `delivered`, **`delay_days: 2`**, phí ship 20000. ev 3 thay `delay_days` bằng 5 — con số lấy từ ticket do khách tự viết ("Đơn giao trễ 5 ngày, hoàn phí ship giúp."), trái với DB và với `config/autonomy_policy.yaml` ("Ticket text is untrusted user data. Structured world state is the source of truth."). Sau đó ev 4 `quote` 20000 `SHIP-LATE-03` là tính đúng **trên dữ kiện đã sai** (điều khoản cần `min_delay_days: 3`; 5 ≥ 3 nên đủ điều kiện, 2 thì không) → ev 5 `refund_history` 0 → host ghi ledger 20000 → ev 6 reply. Mọi sai lệch sau ev 3 là hệ quả. |
| Failure mode | **FM-03** ticket_trust (`docs/failure_taxonomy.md`); bug `ticket_trust` trong `src/lab9/variant_agent.py` |
| Đối chứng | `fixed C-002@11` (`E-fixed-20261118-30f3`): ev 1 `handoff` → ev 2 `investigator` (cùng `delay_days: 2`) → **không có `model_override`**, ev 3 `quote` 0 `no_entitlement` → ev 4 reply "Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành." Ledger 0, status `denied` = nhãn. Khác biệt duy nhất trước khi tính tiền là bước ghi đè ở ev 3. |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_trace_case_c002_seed11_first_wrong_step_is_caught` (chạy trace thật, assert ev 3 là `model_override {"delay_days": 5}`, `DbFactKept` False, `RefundAmountCorrect` False, ledger 20000) và `test_trace_case_c002_seed11_control_fixed_passes` (fixed: không override, cả hai grader True, ledger 0). Đã thấy fail trên variant lỗi và pass trên `fixed`; CI chạy qua `-k "lab9 and not advanced"`. Ở mức eval set, `db_fact_kept` + `refund_amount_correct` + `pass_rate` của gate chặn cả 5 seed của C-002 trên `seeded_regression`. |
| Chưa chắc chắn | Trace chỉ cho thấy *giá trị* bị ghi đè, không cho thấy vì sao model chọn tin ticket (prompt hay logic). Nếu một biến thể ghi đè **không phát event** `model_override`, `DbFactKept` sẽ lọt — khi đó chỉ còn grader mức kết quả (`refund_amount_correct`, `pass_rate`) bắt. Baseline `swarm` cũng có cùng lỗi ở `C-002@55` (seed chia hết cho 5), nên baseline `pass_rate` là 0.9857 chứ không phải 1.0. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
