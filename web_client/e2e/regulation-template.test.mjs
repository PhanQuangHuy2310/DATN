import test from "node:test";
import assert from "node:assert/strict";
import { buildClause, nextArticle } from "../src/regulationTemplate.js";

test("quick template writes clauses the regulation compiler understands", () => {
  assert.equal(
    buildClause({ typeName: "Thanh toán chi phí", cond: "amount", op: "gt", value: "5", act: "manual", approver: "Giám đốc" }, 2),
    "Điều 2: Yêu cầu Thanh toán chi phí có giá trị trên 5 triệu đồng bắt buộc Giám đốc phê duyệt thủ công.",
  );
  assert.equal(
    buildClause({ typeName: "Nghỉ phép", cond: "days", op: "gte", value: "3", act: "acceptance", approver: "Trưởng bộ phận" }),
    "Điều 1: Yêu cầu Nghỉ phép từ 3 ngày trở lên bắt buộc Trưởng bộ phận phê duyệt thủ công kèm nghiệm thu độc lập.",
  );
  assert.equal(
    buildClause({ typeName: "Làm việc từ xa (WFH)", cond: "repeat", value: "4", act: "manual", approver: "Trưởng bộ phận" }),
    "Điều 1: Yêu cầu Làm việc từ xa (WFH) lần thứ 4 trở lên trong tháng bắt buộc Trưởng bộ phận phê duyệt thủ công.",
  );
  assert.equal(buildClause({ typeName: "Hoàn tiền / Đền bù", cond: "all", act: "auto" }),
    "Điều 1: Mọi yêu cầu Hoàn tiền / Đền bù được tự động duyệt.");
});

test("incomplete or unsafe choices produce no clause", () => {
  assert.equal(buildClause({ typeName: "", cond: "amount", op: "gt", value: "5", act: "manual" }), null);
  assert.equal(buildClause({ typeName: "Nghỉ phép", cond: "days", op: "gt", value: "", act: "manual" }), null);
  assert.equal(buildClause({ typeName: "WFH", cond: "repeat", value: "4", act: "auto" }), null);
});

test("next article number follows what is already written", () => {
  assert.equal(nextArticle(""), 1);
  assert.equal(nextArticle("Điều 1: a.\nĐiều 3: b."), 4);
});
