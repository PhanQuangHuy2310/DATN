import test from "node:test";
import assert from "node:assert/strict";
import { freeCode } from "../src/regulationCode.js";

test("a fresh database (REG-001..003, v1.0) is offered REG-004, never a taken code", () => {
  const regs = [{ code: "REG-001" }, { code: "REG-002" }, { code: "REG-003" }];
  assert.equal(freeCode(regs), "REG-004");
  assert.equal(freeCode([...regs, { code: "QC05-6F1D23" }, { code: "reg-014" }]), "REG-015");
  assert.equal(freeCode([]), "REG-001");
});
