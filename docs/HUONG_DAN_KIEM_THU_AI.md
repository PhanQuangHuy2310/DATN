# Hướng dẫn kiểm thử các chức năng AI trên giao diện

Tài liệu này hướng dẫn tự bấm thử từng chức năng AI của EAS, kèm 2 văn bản quy định mẫu để ban hành. Mỗi kịch bản ghi rõ dùng tài khoản nào, bấm gì và kết quả mong đợi. Các kịch bản tự động tương ứng nằm ở `tests/live/`.

## 0. Chuẩn bị

- **Chỉ thử trên máy local** (Docker + Supabase local). Không thử trên Supabase chung: các kịch bản tạo nhiều hồ sơ và bad case thật.
- Bật stack: `docker compose up -d`, rồi chờ `api` và `ai-service` báo healthy (`docker ps`). Phải có **worker** chạy: AI tự duyệt và chuyển quy trình do worker làm, mất 2–10 giây sau khi gửi đơn. Bấm tải lại trang để thấy kết quả.
- Có hai cổng web:
  - **Cổng nhân viên:** http://127.0.0.1:8080
  - **Cổng quản trị:** http://127.0.0.1:8081
- **Mật khẩu chung** của mọi tài khoản bên dưới: `Password@123456`. Admin: `admin@eas.com` (đăng nhập ở cổng quản trị).
- Một trình duyệt chỉ giữ được một phiên đăng nhập. Để đóng nhiều vai cùng lúc, dùng thêm cửa sổ ẩn danh hoặc một trình duyệt khác.
- Tìm hồ sơ theo mã (EAS-2026-xxxxxx) bằng ô **tìm kiếm** trên thanh đầu trang.

### Tài khoản dùng trong các kịch bản (quan hệ quản lý thật trong dữ liệu local)

| Quản lý | Nhân viên của họ | Quản lý cấp trên |
|---|---|---|
| tam.tran@eas.com | loc.dinh, my.luong, nhung.phan | thao.vu |
| binh.le@eas.com | hoa.lam, khang.pham, khoa.bui | tuan.phan |
| lan.ngo@eas.com | khang.to, khoa.le, khoi.dang | chau.nguyen |
| phong.huynh@eas.com | tam.dang, tien.luong | ha.bui |

Mỗi kịch bản dùng người riêng. AI **nhớ** người từng bị thu hồi, nên dùng lại cùng người ở kịch bản khác sẽ cho kết quả khác.

Các loại đơn **A** (AI được phép tự duyệt khi rủi ro ≤ 2) gồm:
- Điều chỉnh chấm công
- Đặt phòng họp
- Thẻ khách ra vào
- WFH
- Nghỉ phép
- Nghỉ phép đặc biệt
- Hoàn tiền / Đền bù

Thanh toán chi phí và Chiết khấu đặc biệt cũng thuộc loại A nhưng có rủi ro 3, nên AI không tự duyệt; AI vẫn kiểm tra bad case và chuyển quy trình cho hai loại này.

### Thứ tự nên làm

- Các kịch bản 1–3 dùng được ngay.
- Kịch bản 4 cần ban hành **Quy chế 05/2026** trước (mục 4.1).
- Kịch bản 5–6 độc lập.
- Kịch bản 7 dùng **Quy định 06/2026**.

| # | Chức năng AI | Kết quả mong đợi |
|---|---|---|
| 1 | Trợ lý AI khi tạo đơn | Gợi ý đúng loại đơn từ tiêu đề; đánh giá rủi ro; tóm tắt hồ sơ |
| 2 | AI tự duyệt + người duyệt thu hồi | Đơn A tự duyệt sau vài giây; thu hồi được trong 24 giờ; lần sau AI nhớ |
| 3 | Bad case vướng hạn chót → chuyển A→B → AI đề xuất xử lý | Đơn nghỉ bị chuyển B, nêu lý do; quản lý duyệt xong thấy đề xuất giao việc hoặc lùi hạn |
| 4 | AI học quy định mới (Quy chế 05/2026) | Cổng nhân viên khóa bảo trì → AI học → thông báo; đơn chia nhỏ chứng từ bị chuyển C |
| 5 | AI học bad case mới từ lý do thu hồi | Lần 1–2: AI hỏi admin; lần 3: AI tự thêm bad case và áp cho người khác |
| 6 | Lý do riêng → AI hỏi admin | AI nói chưa đủ, giải thích, hỏi; admin bấm "Không tạo" |
| 7 | Quy định có câu AI chưa hiểu (Quy định 06/2026) | Câu hiểu được áp dụng ngay; câu khó vào hàng chờ kèm gợi ý của Gemini; admin duyệt thì AI học lại |
| 8 | AI đọc văn bản quy định, trả lỗi, trả lại bản lỗi | Văn bản mâu thuẫn hoặc lỗi ký tự bị chặn kèm lỗi từng câu; học thất bại thì hiệu lực quay về bản cũ, bản lỗi vào "Bị trả lại" để sửa và nạp lại |

---

## Kịch bản 1: Trợ lý AI khi tạo đơn

1. Đăng nhập cổng nhân viên bằng **my.luong**, bấm **Tạo yêu cầu mới**.
2. Ở ô tiêu đề, gõ `bố mất xin nghỉ 3 ngày`.
   - **Mong đợi:** AI tự chuyển sang biểu mẫu **Nghỉ phép đặc biệt** và cho phép quay lại loại cũ.
3. Thử thêm các câu ngắn: `xin wfh thứ 6`, `quên chấm công sáng nay`, `đặt phòng họp 10 người`.
   - **Mong đợi:** gợi ý lần lượt WFH, Điều chỉnh chấm công, Đặt phòng họp.
4. Trong khung **Trợ lý AI**, bấm **Gợi ý & đánh giá rủi ro**.
   - **Mong đợi:** hiện loại đơn AI đề xuất (kèm các khả năng khác nếu AI chưa chắc) và mức rủi ro.
5. Mở một hồ sơ bất kỳ, bấm **AI tóm tắt hồ sơ**.
   - **Mong đợi:** một đoạn tóm tắt ngắn.

## Kịch bản 2: AI tự duyệt và người duyệt thu hồi (AI "sai tối đa 1 lần")

1. Đăng nhập **loc.dinh**, tạo đơn **Làm việc từ xa (WFH)** cho một ngày cách hôm nay khoảng 7 ngày, rồi gửi.
2. Chờ vài giây rồi tải lại trang.
   - **Mong đợi:** hồ sơ chuyển **Hoàn thành**, có ghi chú AI đã tự động duyệt và hạn được thu hồi (24 giờ).
3. Đăng nhập **tam.tran** (quản lý của loc.dinh), tìm theo mã hồ sơ, bấm **Thu hồi duyệt tự động của AI**, nhập lý do, ví dụ `Hôm đó có họp bắt buộc tại văn phòng`.
   - **Mong đợi:** hồ sơ quay về chờ tam.tran duyệt thủ công. Bạn từ chối hoặc duyệt như bình thường.
4. Quay lại **loc.dinh**, tạo thêm một đơn WFH khác ngày.
   - **Mong đợi:** AI **không** tự duyệt mà chuyển đơn sang quy trình B. Khung "AI chuyển quy trình" có nhãn **Đã học từ phản hồi** và ghi "giống ca EAS-… đã được … sửa".
5. Đối chứng: **my.luong** gửi đơn WFH. **Mong đợi:** vẫn được tự duyệt, vì AI chỉ nhớ cho đúng người và đúng loại đơn.

## Kịch bản 3: Bad case vướng hạn chót, chuyển A→B và AI đề xuất xử lý

Tình huống của Quy chế 05 Điều 1: trưởng nhóm xin nghỉ trong khi đang giữ việc sắp đến hạn, và người nhận bàn giao không làm thay được việc đó.

1. **khoa.le** tạo **Thanh toán chi phí** 1.300.000 đ (điền số hóa đơn, tài khoản nhận bất kỳ) và gửi. Bước duyệt đầu tiên rơi vào **lan.ngo**: đây là "việc đang giữ" của lan.ngo.
2. **lan.ngo** tạo **Nghỉ phép** 1 ngày, **ngày mai**, ô người nhận bàn giao chọn **khoa.le**, rồi gửi.
3. Chờ vài giây rồi tải lại hồ sơ nghỉ.
   - **Mong đợi:** khung **"AI · Hồ sơ được chuyển từ quy trình A sang quy trình B"**, liệt kê:
     - nguyên nhân **BC_DEADLINE_CONFLICT**, nói rõ khoa.le không đủ thẩm quyền làm thay, vì chính khoa.le là người gửi việc đó;
     - dòng **"Vì sao là bad case: …"**;
     - nếu đã ban hành Quy chế 05, có thêm các điều luật liên quan.
4. **chau.nguyen** (quản lý của lan.ngo) mở hồ sơ nghỉ và **duyệt**.
   - **Mong đợi:** xuất hiện bảng **"AI đề xuất cách xử lý công việc đang dở"**, gồm việc đang giữ, người được AI xếp hạng 1 kèm điểm và lý do, và phương án lùi hạn.
5. Giữ lựa chọn AI gợi ý, bấm **Xác nhận**.
   - **Mong đợi:** bước duyệt hồ sơ thanh toán của khoa.le chuyển sang người được chọn. Nhật ký ghi "AI đề xuất – quản lý xác nhận".
   - Thử chọn người khác hạng 1: lần sau AI xếp người bạn chọn lên đầu cho lan.ngo.
6. Thử nút **AI chuyển nhầm** trên khung chuyển quy trình, nhập lý do.
   - **Mong đợi:** lần sau lan.ngo gặp đúng tình huống này, đơn không bị chuyển nữa.
   - Riêng trường hợp quy định bắt buộc chuyển thì AI vẫn chuyển.

## Kịch bản 4: AI học quy định mới

### 4.1 Ban hành Quy chế 05/2026 (cổng quản trị, tài khoản admin)

**Quy định → Thêm quy định mới**:
- Mã: `QC05-2026`
- Tiêu đề: `Quy chế 05/2026 về nghỉ phép, chấm công và hạn mức tài chính`
- Nội dung: dán nguyên văn đoạn dưới đây, rồi bấm **Ban hành & Huấn luyện AI**.

```
Điều 1 (Chặn duyệt tự động Nghỉ phép khi vướng hạn chót công việc): Đối với yêu cầu Nghỉ phép hoặc Nghỉ phép đặc biệt kéo dài từ 1 ngày trở lên trong giai đoạn nhân sự đang giữ tác vụ có hạn chót gấp trong 24 giờ chưa bàn giao, hệ thống không được tự động duyệt mà bắt buộc phải qua Trưởng bộ phận và Nhân sự phê duyệt thủ công. Điều 2 (Chặn lạm dụng Điều chỉnh chấm công lặp lại có hệ thống): Đối với yêu cầu Điều chỉnh chấm công khi nhân sự giải trình quên chấm công, đi muộn hoặc về sớm lặp lại từ lần thứ 4 trong tháng, hệ thống không tự động duyệt và bắt buộc Trưởng bộ phận phê duyệt thủ công. Điều 3 (Kiểm soát hạn mức Thanh toán chi phí và Quyết toán tạm ứng): Đối với yêu cầu Thanh toán chi phí hoặc Quyết toán tạm ứng có giá trị từ 20 triệu đồng trở lên, hệ thống không được tự động phê duyệt mà phải qua Kế toán kiểm soát và trình Ban Giám đốc phê duyệt. Điều 4 (Chống chia nhỏ chứng từ Tạm ứng và Thanh toán để lách hạn mức): Đối với đề xuất Thanh toán chi phí, Tạm ứng chi phí (<10tr) và Tạm ứng chi phí (10-50tr) có giá trị từ 15 triệu đồng trở lên hoặc có dấu hiệu chia nhỏ hóa đơn liên tiếp, hệ thống bắt buộc trình Kế toán và Ban Giám đốc phê duyệt thủ công kèm nghiệm thu độc lập. Điều 5 (Kiểm soát Hoàn tiền và Làm việc từ xa rủi ro cao): Đối với yêu cầu Hoàn tiền / Đền bù có giá trị trên 2 triệu đồng, hệ thống không được tự động duyệt mà bắt buộc phải được phê duyệt thủ công. Đối với yêu cầu Làm việc từ xa (WFH) kéo dài trên 2 ngày, hệ thống bắt buộc phải qua Trưởng bộ phận phê duyệt thủ công.
```

**Mong đợi:**
- Trong lúc AI học (khoảng vài chục giây), cổng nhân viên hiện **màn hình chờ bảo trì**, không tạo đơn được.
- Học xong thì cổng mở lại. Người dùng nhận **thông báo** "quy định mới" kèm hướng dẫn.
- Trang **Quy định** (cổng quản trị) ghi phiên bản mới và trạng thái học của AI.
- AI hiểu các điều có điều kiện, ví dụ "đang giữ việc có hạn trong 24 giờ, chưa bàn giao". Nó **không** chặn tràn lan kiểu "chặn mọi đơn nghỉ phép".

### 4.2 Kiểm tra quy định đã có hiệu lực

| Thử | Tài khoản | Mong đợi |
|---|---|---|
| 3 đơn **Thanh toán chi phí** 9.500.000 đ, gửi liên tiếp | khang.to | Đơn 1 giữ quy trình A. Từ đơn 2 trở đi bị **chuyển C** (kế toán xử lý, quản lý nghiệm thu độc lập), nguyên nhân chia nhỏ chứng từ (Điều 4 + BC_SPLIT_AMOUNT_EVASION) |
| Lặp lại kịch bản 3 | lan.ngo | Ngoài BC_DEADLINE_CONFLICT, khung chuyển quy trình liệt kê thêm điều luật Điều 1 của QC05 |
| **Điều chỉnh chấm công** lần thứ 4 trong tháng | khoa.bui | 3 lần đầu được tự duyệt; lần 4 bị **chuyển B** (Điều 2) |
| Trang **Quy định nội bộ** (cổng nhân viên) | bất kỳ | Thấy QC05-2026 ở bản mới nhất |

## Kịch bản 5: AI học bad case mới từ lý do thu hồi (yêu cầu của trưởng nhóm)

Ý tưởng: 3 người duyệt độc lập cùng thu hồi đơn WFH vì người gửi **báo quá sát giờ**. Kiểu rủi ro này chưa có trong danh mục.

1. Ba nhân viên, mỗi người gửi một đơn **WFH cho ngày mai** và đều được AI tự duyệt:
   - hoa.lam (quản lý binh.le)
   - khang.pham (quản lý binh.le)
   - khoi.dang (quản lý lan.ngo)
2. Lần lượt từng quản lý thu hồi đơn của nhân viên mình, nhập đúng các lý do sau:
   - binh.le thu hồi đơn của hoa.lam: `Báo WFH quá sát giờ, gửi tối hôm trước cho sáng hôm sau, phòng không kịp sắp xếp.`
   - binh.le thu hồi đơn của khang.pham: `Xin làm từ xa sát ngày như vậy thì không kịp bố trí người họp thay.`
   - lan.ngo thu hồi đơn của khoi.dang: `Cứ báo WFH đột xuất, không báo trước đủ thời gian để sắp xếp công việc.`
3. Sau **lần thu hồi thứ 1 và thứ 2**, mở cổng quản trị: **Quy định → AI học từ phản hồi → Danh mục bad case → Chờ admin**.
   - **Mong đợi:** thẻ "Báo trước quá sát giờ (WFH_REQ)", gồm:
     - **AI nhận ra khi:** số giờ báo trước ≤ 24 giờ;
     - **AI đánh giá: Chưa đủ để AI tự tạo bad case vì: …** (ví dụ mới 1/3 lần, mới 1/2 người duyệt), kèm danh sách ✓/✗ từng tiêu chí;
     - **AI hỏi: Có tạo bad case … không?**;
     - lý do của từng người duyệt.

   Đừng bấm gì, để AI tự quyết ở lần thứ 3.
4. Sau **lần thu hồi thứ 3**, tải lại trang.
   - **Mong đợi:** thẻ chuyển sang tab **Đang dùng**, nguồn **AI tự học**, với câu "Đủ để thành bad case: 3 lần thu hồi từ 3 người gửi, 2 người duyệt…".
5. **khoa.bui** (chưa từng bị thu hồi) gửi **WFH cho ngày mai**.
   - **Mong đợi:** AI không tự duyệt mà **chuyển B**. Khung chuyển quy trình có nhãn **Bad case AI học được**, kèm dòng **"Vì sao là bad case: Người duyệt đã thu hồi … vì: …"**.
6. Đối chứng: **nhung.phan** gửi WFH cho ngày cách hôm nay khoảng 10 ngày. **Mong đợi:** vẫn được tự duyệt.
7. Dọn sau khi thử: trong **Danh mục bad case**, bấm **Ngưng dùng** ở thẻ vừa tạo.

## Kịch bản 6: Lý do riêng của hồ sơ, AI hỏi admin

1. **my.luong** gửi WFH khoảng 5 ngày nữa (được tự duyệt). **tam.tran** thu hồi với lý do: `Em ghi thiếu danh sách công việc trong ngày, bổ sung rồi gửi lại nhé.`
2. Vào **Danh mục bad case → Chờ admin**.
   - **Mong đợi:** thẻ "Lý do riêng: …", kèm câu **"Chưa đủ để AI tự tạo bad case vì: AI hiểu lý do là riêng của từng hồ sơ…"** và câu hỏi cho admin.
3. Bấm **Không tạo**, nhập lý do. **Mong đợi:** thẻ chuyển sang tab **Không tạo**.
4. Biến thể: **tam.tran** thu hồi đơn WFH đối chứng của **nhung.phan** (kịch bản 5, bước 6) với lý do khớp bad case có sẵn: `Tháng này bạn ấy làm từ xa quá nhiều buổi rồi, cần lên văn phòng.`
   - **Mong đợi:** AI không tạo thẻ mới mà ghi bằng chứng vào **BC_WFH_FREQUENT** có sẵn (tab **Đang dùng**, mục "Lý do người duyệt đã nêu"), kèm **"Vì sao AI bỏ sót: hồ sơ chưa vượt ngưỡng… (mới 1 đơn/tháng, ngưỡng 8)"**.

## Kịch bản 7: Quy định có câu AI chưa hiểu (Quy định 06/2026)

Cổng quản trị, **Quy định → Thêm quy định mới**:
- Mã: `QD06-2026`
- Tiêu đề: `Quy định 06/2026 về hoàn tiền, làm việc từ xa và chiết khấu`
- Nội dung:

```
Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 5 triệu đồng không được tự động duyệt, bắt buộc Kế toán phê duyệt thủ công kèm nghiệm thu độc lập. Điều 2: Yêu cầu Làm việc từ xa (WFH) lần thứ 4 trở lên trong tháng bắt buộc Trưởng bộ phận phê duyệt thủ công. Điều 3: Phê duyệt chiết khấu thương mại đặc biệt từ 15% trở lên phải qua Ban Giám đốc. Điều 4: Yêu cầu Đặt phòng họp tại khu vực tầng 10 phải được Hành chính duyệt thủ công. Điều 5: Nhân viên nên đến văn phòng trước 8 giờ 30 phút.
```

Các điều đã được chạy thử qua trình biên dịch quy định của AI:

| Điều | AI hiểu thành | Cách thử | Mong đợi |
|---|---|---|---|
| 1 | Hoàn tiền > 5 triệu: không tự duyệt, **chuyển C** | **tien.luong** gửi Hoàn tiền 6.000.000 đ, rồi một đơn 1.500.000 đ | Đơn 6 triệu chuyển C (kế toán xử lý, có nghiệm thu). Đơn 1,5 triệu vẫn tự duyệt |
| 2 | WFH lần thứ 4 trở lên trong tháng: **chuyển B** | **tam.dang** (chưa có đơn WFH nào trong tháng) gửi 4 đơn WFH, mỗi đơn một ngày khác nhau | 3 đơn đầu tự duyệt, đơn thứ 4 chuyển B |
| 3 | **Chưa hiểu** (điều kiện phần trăm nằm ngoài khả năng của trình biên dịch) | Xem **Quy định → AI học từ phản hồi → Câu quy định chờ duyệt cách hiểu** | Câu này nằm trong hàng chờ, kèm luật **Gemini đề xuất** dạng JSON. Sửa nếu cần rồi bấm **Duyệt luật, AI học lại**. AI học lại và áp dụng |
| 4 | **Chưa hiểu** (điều kiện khu vực) | Cùng hàng chờ | Bấm **Từ chối** và ghi lý do, AI bỏ qua câu này |
| 5 | Không phải yêu cầu kiểm soát phê duyệt | – | AI bỏ qua, không chặn gì, không đưa vào hàng chờ |

Điều 3 và 4 cần mạng để gọi Gemini. Không có mạng thì câu vẫn vào hàng chờ, chỉ thiếu gợi ý; admin tự soạn luật JSON.

---

## Kịch bản 8: AI đọc văn bản quy định, trả lỗi và trả lại bản lỗi

Nguyên tắc: quy định có lỗi thì **không** được áp dụng. Hiệu lực (văn bản hiển thị và bộ luật AI) giữ ở bản đã áp dụng gần nhất. Bản lỗi được giữ lại kèm **danh sách lỗi chỉ rõ từng câu** để admin sửa rồi nạp lại.

**8.1 Văn bản tự mâu thuẫn bị chặn ngay khi ban hành.** Ở cổng quản trị, vào **Quy định → Thêm quy định mới**, mã `QD07-2026`, nội dung:

```
Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 5 triệu đồng được phép tự động duyệt. Điều 2: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 3 triệu đồng không được tự động duyệt.
```

- Bấm **AI kiểm tra trước**.
  - **Mong đợi:** khung đỏ "AI phát hiện 1 lỗi", loại **Mâu thuẫn**: "Điều 1 cho AI tự duyệt (số tiền > 5.000.000), nhưng Điều 2 bắt duyệt thủ công (số tiền > 3.000.000)…", kèm trích nguyên văn hai câu.
- Bấm **Ban hành** vẫn bị từ chối với cùng danh sách lỗi.
  - **Mong đợi:** không lưu, không khoá cổng nhân viên.
- Sửa Điều 1 thành `… trên 2 triệu đồng được phép tự động duyệt nếu …`, hoặc xóa Điều 1, rồi kiểm tra lại.
  - **Mong đợi:** "AI không thấy lỗi chặn".

**8.2 Lỗi ký tự.** Dán một đoạn bị hỏng mã hóa, ví dụ `YÃªu cáº§u Nghá»‰ phÃ©p…`, hoặc bị mất dấu, ví dụ `Ngh? ph?p`.
- **Mong đợi:** lỗi **Lỗi ký tự**, kèm hướng dẫn lưu lại file dạng UTF-8.

**8.3 Mâu thuẫn với quy định đang hiệu lực.** Sau khi ban hành QC05-2026 (kịch bản 4), thử ban hành `Điều 1: Yêu cầu Làm việc từ xa (WFH) được tự động duyệt.`
- **Mong đợi:** lỗi mâu thuẫn, chỉ ra **Điều 5 của QC05-2026**.

**8.4 Cảnh báo không chặn.**
- Câu AI chưa hiểu (phần trăm, khu vực) và câu trùng luật với văn bản khác chỉ hiện **lưu ý** màu vàng.
- Vẫn ban hành được.
- Câu chưa hiểu vào hàng chờ duyệt của admin, như kịch bản 7.

**8.5 Trả lại khi AI học thất bại.** Chỉ thử trên local.
1. Ban hành một quy định hợp lệ, chờ áp dụng xong.
2. Chạy `docker compose stop ai-service`, rồi **sửa** quy định đó.
3. Chờ khoảng 2 phút. AI thử lại 3 lần rồi bỏ cuộc.
4. Chạy `docker compose start ai-service`.

**Mong đợi:**
- Nội dung quy định trên trang **quay về bản đã áp dụng**. Lịch sử phiên bản ghi "Trả lại bản … khôi phục nội dung bản …".
- Cổng nhân viên được mở khoá.
- Admin nhận thông báo **"Quy định … bị trả lại: AI chưa học được"**.
- Đầu trang Quy định có mục **Quy định bị trả lại**, gồm nội dung bản sửa, nguyên nhân và hai nút:
  - **Sửa và nạp lại:** mở form điền sẵn nội dung bị trả lại kèm danh sách lỗi. Nạp lại thành công thì mục này tự đóng.
  - **Bỏ qua:** đóng mục này, phải ghi lý do.

Kiểm thử tự động tương ứng: `tests/live/test_regulation_rejection.py` (RV-01…RV-05).

## Xem AI đã làm gì

- **Trên hồ sơ:** khung **"AI · Hồ sơ được chuyển từ quy trình …"** (nguyên nhân, vì sao là bad case). Bảng **"AI đề xuất cách xử lý…"** chỉ hiện cho quản lý duyệt. Nhật ký hồ sơ ghi các hành động AI_ESCALATED, AI_LEARNED_FROM_FEEDBACK, AI_BAD_CASE_LEARNED/CANDIDATE…
- **Cổng quản trị → Quy định → AI học từ phản hồi:**
  - danh mục bad case (chờ admin / đang dùng / không tạo / đã ngưng);
  - hàng chờ câu quy định;
  - số phản hồi đã ghi nhận;
  - nút **Học dồn ngay**: huấn luyện lại mô hình xếp hạng người nhận việc, chỉ thay mô hình khi không kém mô hình cũ.
- **Cổng quản trị → Quy định:** lịch sử phiên bản quy định và trạng thái học của AI.

## Khi kết quả khác mong đợi

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| Đơn A không được tự duyệt | Người đó từng bị thu hồi (AI nhớ, đúng như thiết kế); hoặc đã có quá nhiều đơn cùng loại trong tháng (bad case khác); hoặc worker chưa chạy (`docker ps`) |
| Đơn nghỉ phép bị từ chối tự duyệt vì quỹ phép | Hết phép năm trong hệ thống HR mô phỏng; chọn người khác |
| Kịch bản 5 không tự tạo bad case ở lần 3 | Xem thẻ ứng viên: AI ghi rõ thiếu tiêu chí nào (số lần, số người, độ phủ…) và chờ admin quyết |
| Đơn chấm công, chi phí, hoàn tiền hoặc chiết khấu bị chuyển B vì **BC_OFF_HOURS_BULK** | Bạn gửi từ 3 đơn ngoài giờ hành chính (sau 17:30 hoặc cuối tuần) trong 7 ngày. Đây là bad case có sẵn; thử trong giờ hành chính hoặc đổi người |
| Không thấy bảng đề xuất xử lý | Chỉ người duyệt hồ sơ (chau.nguyen trong kịch bản 3) mới thấy, và chỉ sau khi đã duyệt |

Kiểm thử tự động tương đương: `tests/live/test_ai_escalation.py`, `test_ai_feedback_learning.py`, `test_bad_case_learning.py`. Báo cáo số đo: `ai_service/training/data/*_report.md`.
