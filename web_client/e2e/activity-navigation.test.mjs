import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { activityLabel } from "../src/activityLabels.js";

const read = (file) => readFileSync(new URL(file, import.meta.url), "utf8");

test("activity labels are meaningful for workflow transitions", () => {
  for (const key of ["DRAFT_CREATED", "REQUEST_SUBMITTED", "APPROVAL_APPROVE", "ACCEPTANCE_REWORK"]) {
    assert.notEqual(activityLabel(key), "Hoạt động hồ sơ");
  }
});

test("opening a notification uses progress and marks it read", () => {
  const admin = read("../src/components/Admin.jsx");
  const app = read("../src/App.jsx");
  assert.match(admin, /notifications\/\$\{item\.id\}\/read/);
  assert.match(app, /<Notifications onOpen=\{\(id\) => openRequest\(id, "progress"\)\}/);
  assert.match(app, /initialTab=\{selectedTab === "progress"/);
});

test("activity outbox is not recreated by frontend", () => {
  const admin = read("../src/components/Admin.jsx");
  assert.doesNotMatch(admin, /INSERT INTO eas\.notification/);
});
