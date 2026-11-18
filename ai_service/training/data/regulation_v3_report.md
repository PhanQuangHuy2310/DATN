# Trình biên dịch quy định v3 và luật thay thế quy định cũ: báo cáo (18/11/2026)

Yêu cầu: "cho học hết các trường hợp có thể": AI hiểu mọi kiểu điều kiện, xử lý mọi tình huống thay thế, có thêm các ca oái oăm; quy định cũ đã bị thay thì **bỏ vĩnh viễn**.

## Bộ test (viết tay, băm trước khi cài v3)

`regulation_v3_test.json`, sha256 `e7ef2366…`, commit `91dc93d`, gồm:
- **40 câu quy định:**
  - cận trên, khoảng, phần trăm;
  - địa điểm;
  - khung thời gian 14 / 90 ngày, quý, năm;
  - "ngày đã quá N ngày";
  - ngày hiệu lực;
  - ca oái oăm: "không dưới", "từ … trở xuống", "1,5 tỷ", "500 nghìn", "15 phần trăm", chữ "từ" đứng trước ngày tháng, điều kiện định tính phải bỏ qua.
- **12 tình huống thay thế:** ban hành / sửa / bãi bỏ lần lượt, rồi thử 25 hồ sơ.

## Kết quả

| Bộ máy | 40 câu | 12 tình huống thay thế (25 hồ sơ thử) |
|---|---|---|
| v2 (trước đợt này) | 9/40 | 8/12 (20/25) |
| **v3, lần chấm đầu** | **39/40** | **12/12 (25/25)** |
| v3 sau 1 sửa (xem dưới) | 40/40 | 12/12 (25/25) |

Ở v2, ngoài các câu không hiểu, còn hai câu **chặn tràn lan**: "Hoàn tiền cho khách hàng thân thiết" và "phòng họp dưới 10 người" bị dịch thành "chặn mọi đơn loại đó". v3 bỏ qua các câu này và đưa vào hàng chờ duyệt của admin.

## Thay đổi đưa ra sau khi đã chấm (ghi lại cho trung thực)

1. **V22** "từ 3 đến 5 ngày": đơn vị viết một lần được dùng cho cả hai đầu khoảng. Câu này sai ở lần chấm đầu, đã sửa.
2. **Kiểm tra hồi quy trên bộ test cũ** (`regulation_clauses_test.json`, 30 câu, v2 đạt 29/30) lộ ra hai lỗi v3 mới gây ra, đã sửa:
   - "chưa bàn giao **cho người khác**" bị tưởng là điều kiện định tính, nên mất luật;
   - "Nghỉ phép **dưới 1 ngày**" bị dịch thành "≤ 0 ngày". Nghỉ nửa ngày không biểu diễn được vì số ngày là số nguyên, nên câu này bị bỏ qua.

   Bộ test cũ giờ đạt **28/30**. Hai câu khác biệt (T27 "ngày đã quá 30 ngày", T28 "từ 20%") là **cố ý**: v3 hiểu được, còn nhãn cũ ghi "không hiểu" theo giới hạn của v2.
3. "Mua sắm từ **15% ngân sách**": phần trăm của một đại lượng khác, không phải mức chiết khấu của hồ sơ, nên được bỏ qua.

## Kiểm thử thật (`tests/live/test_regulation_supersede.py`): 6/6

| Ca | Kết quả |
|---|---|
| SP-01 | Quy định hoàn tiền "> 4 triệu": đơn 5 triệu chuyển C |
| SP-02 | Kiểm tra trước quy định mới "> 6 triệu": AI báo "Sẽ thay thế…" |
| SP-03 | Ban hành xong: luật 4 triệu rời bộ luật AI, đơn 5 triệu không còn chuyển, đơn 7 triệu chuyển C, người dùng được thông báo |
| SP-04 | Văn bản tự mâu thuẫn vẫn bị chặn |
| SP-05 | Chiết khấu "từ 15%": đơn 20% chuyển C, đơn 10% giữ A |
| SP-06 | "Ngày đã quá 7 ngày": luật khớp đơn sửa công cho 10 ngày trước, không khớp đơn cho hôm qua |

Lần chạy đầu, SP-05 và SP-06 trượt vì **chính kịch bản test**, không phải lỗi luật:
- hai đơn chiết khấu cùng tên khách nên dính bad case "chiết khấu lặp lại";
- chạy lúc 20 giờ nên dính bad case "gửi hàng loạt ngoài giờ".

AI làm đúng trong cả hai trường hợp. Đã sửa kịch bản để kiểm tra riêng luật quy định.

## Dò ca oái oăm (19/11/2026): 6 lỗi an toàn, đã sửa

Bộ ca ranh giới `tests/test_edge_cases.py` (bad case, bộ máy luật, trình biên dịch) tìm ra các câu mà trình biên dịch **mất điều kiện
nhưng vẫn sinh luật**. Lỗi nặng nhất: luật thành "chặn MỌI đơn của loại đó".

| Câu | Trước khi sửa | Sau khi sửa |
|---|---|---|
| "trên **50tr**" | mất ngưỡng, chặn mọi đơn thanh toán | > 50.000.000 (hiểu thêm tr / trđ / k) |
| "trên **-5 triệu**" | mất ngưỡng, chặn mọi đơn | không sinh luật, admin duyệt ("số không rõ cận trên/dưới") |
| "**không** bắt buộc duyệt thủ công" | đọc thành bắt buộc | không sinh luật; AI không tự nới lỏng kiểm soát |
| "trên 50 triệu **và dưới 20 triệu**" | luật khoảng rỗng | không sinh luật ("khoảng rỗng") |
| "trên **150%**", ngày bắt đầu **sau** ngày hết hiệu lực | luật vô nghĩa | không sinh luật, kèm lý do |
| "Chiết khấu thương mại đặc biệt" (tên loại thiếu "Phê duyệt") | không nhận ra loại | khớp, nếu phần còn lại của tên có ≥ 4 từ |
| Câu viết **không dấu** | bỏ qua im lặng | admin thấy lý do "câu viết không dấu" |

Nguyên tắc: không chắc thì **không** sinh luật, đưa câu lên admin kèm lý do.

Hồi quy sau khi sửa:
- bộ v3: 40/40;
- thay thế: 12/12;
- bộ cũ: 28/30, không đổi.

## Giới hạn còn lại

- Điều kiện theo số người, nhóm khách hàng, ngày lễ, "hồi tố" chung chung vẫn **không** tự hiểu. Câu có các điều kiện này vào hàng chờ duyệt cách hiểu của admin.
- Địa điểm so khớp theo chữ trong các trường địa điểm của biểu mẫu. "tầng 10" chỉ khớp nếu biểu mẫu có ghi tầng.
- Bộ test do cùng một người viết với người cài. Bộ test băm trước giảm thiên lệch nhưng không loại bỏ hẳn.
