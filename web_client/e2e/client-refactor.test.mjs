import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { allowedStages, requestStage, STATUS_STAGES } from '../src/clientWorkflow.js';
import { visiblePages, canNavigate } from '../src/rolePolicy.js';

const employee = { roles: ['REQUESTER'] };
const approver = { roles: ['APPROVER'] };

test('employee sees personal workflow stages, not unauthorized approval queues', () => {
  assert.deepEqual(allowedStages(employee).map(s=>s.key), ['mine','completed','drafts']);
  assert.deepEqual(allowedStages(approver).map(s=>s.key), ['approval']);
  assert.ok(allowedStages({roles:['REQUESTER','APPROVER','EXECUTOR','ACCEPTOR']}).length===6);
});
test('workflow status classification keeps rejected and canceled requests visible', () => {
 const values = {DRAFT:'drafts',PENDING_APPROVAL:'approval',NEEDS_INFO:'approval',READY_FOR_EXECUTION:'execution',IN_PROGRESS:'execution',WAITING_FOR_ACCEPTANCE:'acceptance',COMPLETED:'completed',REJECTED:'rejected',CANCELLED:'cancelled'};
 for(const [status,stage] of Object.entries(values)) assert.equal(requestStage(status),stage,status);
 for(const stage of Object.values(values)) assert.ok(STATUS_STAGES.includes(stage));
});
test('client routes exclude unrelated profiles and administration while preserving organization chart', () => {
 const pages=visiblePages(['REQUESTER']);
 assert.ok(pages.includes('org-client'));
 assert.ok(!pages.includes('history') && !pages.includes('identity') && !pages.includes('request-catalog') && !pages.includes('ops'));
 assert.equal(canNavigate(['REQUESTER'],'org-chart'),false);
});
test('dashboard requests a strictly requester-scoped report, with backend scope validation', () => {
 const dashboard=readFileSync(new URL('../src/components/ClientDashboard.jsx',import.meta.url),'utf8');
 const backend=readFileSync(new URL('../../api_core/workflow/reporting.py',import.meta.url),'utf8');
 assert.match(dashboard,/scope:"mine"/);
 assert.match(backend,/scope not in \(None, "mine"\)/);
 assert.match(backend,/r.requester_id = %s::uuid/);
});
test('new request supports flexible templates only when enabled by backend',()=>{
 const selector=readFileSync(new URL('../src/components/RequestTypeMenu.jsx',import.meta.url),'utf8');
 assert.match(selector,/Tạo yêu cầu khác/);
 assert.match(selector,/item.available/);
 assert.match(selector,/Chưa có mẫu linh hoạt được công bố/);
});

test('AI process uses real request workflow and on-demand model calls, not a static image', () => {
 const component=readFileSync(new URL('../src/components/AiProcessGuide.jsx',import.meta.url),'utf8');
 assert.match(component,/\/api\/v1\/requests\?tab=/);
 assert.match(component,/\/api\/v1\/requests\/\$\{currentId\}/);
 assert.match(component,/\/api\/v1\/ai\/classify/);
 assert.match(component,/\/api\/v1\/ai\/risk-score/);
 assert.ok(!component.includes('ai-process-image'));
 assert.match(component,/fallback_used/);
});
test('organization exposes manager relationships in same department without changing form selector schema', () => {
 const backend=readFileSync(new URL('../../api_core/catalog/views.py',import.meta.url),'utf8');
 const view=readFileSync(new URL('../src/components/ClientOrgChart.jsx',import.meta.url),'utf8');
 assert.match(backend,/m\.department_id = u\.department_id AND m\.is_active/);
 assert.match(backend,/"organization": people/);
 assert.match(backend,/"items": choices/);
 assert.match(view,/manager_id/);
 assert.match(view,/organization/);
});
test('period toolbar aligns labels and all actions in shared grid',()=>{
 const view=readFileSync(new URL('../src/components/DashboardOverview.jsx',import.meta.url),'utf8');
 const css=readFileSync(new URL('../src/client-refactor.css',import.meta.url),'utf8');
 assert.match(view,/overview-quick-group/);
 assert.match(view,/overview-apply-group/);
 assert.match(css,/\.overview-filter \{display:grid!important/);
});
