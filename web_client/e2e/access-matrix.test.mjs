import test from "node:test";
import assert from "node:assert/strict";
import { buildAccessMatrix } from "../src/accessMatrix.js";

const definitions = [{role:"REQUESTER",name:"Người yêu cầu"}, {role:"APPROVER",name:"Người phê duyệt"}];
const endpoints = [
  {domain:"Yêu cầu",method:"GET",path:"/requests",roles:["REQUESTER","APPROVER"]},
  {domain:"Yêu cầu",method:"POST",path:"/request-drafts",roles:["REQUESTER"]},
  {domain:"Phê duyệt",method:"POST",path:"/approvals",roles:["APPROVER"]},
  {domain:"Thông báo",method:"GET",path:"/notifications",roles:["AUTHENTICATED"]},
  {domain:"Báo cáo",method:"GET",path:"/reports",roles:["PARTICIPANT"]},
];

test("matrix uses only explicit role declarations", () => {
  const matrix = buildAccessMatrix(definitions, endpoints);
  assert.deepEqual(matrix.domains, ["Yêu cầu","Phê duyệt"]);
  assert.equal(matrix.documentedCount,3);
  assert.equal(matrix.rows[0].cells[0].kind,"both");
  assert.equal(matrix.rows[0].cells[0].reads,1);
  assert.equal(matrix.rows[0].cells[0].writes,1);
  assert.equal(matrix.rows[1].cells[0].kind,"read");
  assert.equal(matrix.rows[1].cells[1].kind,"write");
  assert.equal(matrix.rows[0].cells[1].kind,"none");
});

test("matrix does not expand PARTICIPANT/AUTHENTICATED aliases into grants", () => {
  const matrix = buildAccessMatrix(definitions,[{domain:"Khác",method:"GET",roles:["PARTICIPANT","AUTHENTICATED"]}]);
  assert.deepEqual(matrix.domains,[]);
  assert.equal(matrix.documentedCount,0);
  assert.equal(matrix.rows.length,2);
});

test("empty catalog remains a valid empty chart", () => {
  assert.deepEqual(buildAccessMatrix([], []), {domains:[],rows:[],documentedCount:0});
});
