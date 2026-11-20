import test from "node:test";
import assert from "node:assert/strict";
import { bytesToBase64, IMPORT_TEMPLATE, lineDiff } from "../src/regulationImport.js";

test("history diff marks the changed article only", () => {
  const before = "Điều 1: A dưới 5 triệu tự duyệt.\nĐiều 2: Nghỉ phép từ 10 ngày cần Giám đốc.";
  const after = "Điều 1: A dưới 5 triệu tự duyệt.\nĐiều 2: Nghỉ phép từ 12 ngày cần Giám đốc.\nĐiều 3: Mới.";
  assert.deepEqual(lineDiff(before, after), [
    { kind: "same", text: "Điều 1: A dưới 5 triệu tự duyệt." },
    { kind: "del", text: "Điều 2: Nghỉ phép từ 10 ngày cần Giám đốc." },
    { kind: "add", text: "Điều 2: Nghỉ phép từ 12 ngày cần Giám đốc." },
    { kind: "add", text: "Điều 3: Mới." },
  ]);
  assert.deepEqual(lineDiff("x", "x"), [{ kind: "same", text: "x" }]);
});

test("template and base64 survive Vietnamese text", () => {
  assert.match(IMPORT_TEMPLATE, /^QUY ĐỊNH/);
  assert.match(IMPORT_TEMPLATE, /\nMã: QD-MAU-01\n/);
  const bytes = new TextEncoder().encode(IMPORT_TEMPLATE);
  assert.equal(Buffer.from(bytesToBase64(bytes), "base64").toString("utf-8"), IMPORT_TEMPLATE);
});
