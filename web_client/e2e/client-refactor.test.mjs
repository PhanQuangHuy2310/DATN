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
 assert.match(dashboard,/scope:\s*"mine"/);
 assert.match(backend,/scope not in \(None, "mine"\)/);
 assert.match(backend,/r.requester_id = %s::uuid/);
});
test('new request supports flexible templates only when enabled by backend',()=>{
 const selector=readFileSync(new URL('../src/components/RequestTypeMenu.jsx',import.meta.url),'utf8');
 assert.match(selector,/Tạo yêu cầu khác/);
 assert.match(selector,/item.available/);
 assert.match(selector,/Chưa có mẫu linh hoạt được công bố/);
});

test('AI process uses real request workflow and persisted per-request assessments, not a static image', () => {
 const component=readFileSync(new URL('../src/components/AiProcessGuide.jsx',import.meta.url),'utf8');
 assert.match(component,/\/api\/v1\/requests\?tab=/);
 assert.match(component,/\/api\/v1\/requests\/\$\{currentId\}/);
 // Per-request, persisted assessment (with fallback labelling) instead of session-only calls.
 assert.match(component,/<AiAssessmentPanel/);
 assert.ok(!component.includes('ai-process-image'));
 const panel=readFileSync(new URL('../src/components/RequestProgress.jsx',import.meta.url),'utf8');
 assert.match(panel,/fallback_used/);
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
test('each portal renders in its own mode, never the unrestricted "unified" fallback', () => {
 const client=readFileSync(new URL('../src/main.jsx',import.meta.url),'utf8');
 const admin=readFileSync(new URL('../../web_admin/src/main.jsx',import.meta.url),'utf8');
 assert.match(client,/<App portal="client" \/>/);
 assert.match(admin,/<App portal="admin"(\s+adminScreens=\{adminScreens\})?\s*\/>/);
});
test('administrative accounts stay system-only on the client portal', () => {
 const app=readFileSync(new URL('../src/App.jsx',import.meta.url),'utf8');
<<<<<<< HEAD
 assert.match(app,/portal === "client" && !canUsePortal\(user\.roles, "client"\)/);
=======
 assert.match(app,/portal === "client" && \(user\.email === "admin@eas\.com" \|\| !canUsePortal\(user\.roles, "client"\)\)/);
>>>>>>> origin/main
});
test('admin overview shows API data, not hardcoded head counts', () => {
 const app=readFileSync(new URL('../src/App.jsx',import.meta.url),'utf8');
 assert.ok(!/\|\| 42|\|\| 8;|ISO\/IEC 27001|2\.0 LTS/.test(app));
 assert.match(app,/<AdminDashboard navigate=\{navigate\} \/>/);
 const pages=readFileSync(new URL('../src/components/AdminPages.jsx',import.meta.url),'utf8');
 assert.match(pages,/\/api\/v1\/admin\/overview\?/);
 assert.match(pages,/\/api\/v1\/admin\/diagnostics/);
});
test('request detail and editor surface real progress, route preview and persisted AI history', () => {
 const detail=readFileSync(new URL('../src/components/RequestDetail.jsx',import.meta.url),'utf8');
 const editor=readFileSync(new URL('../src/components/RequestEditor.jsx',import.meta.url),'utf8');
 const preview=readFileSync(new URL('../src/components/RoutePreview.jsx',import.meta.url),'utf8');
 const ai=readFileSync(new URL('../src/components/RequestProgress.jsx',import.meta.url),'utf8');
 assert.match(detail,/<ProgressSummary progress=\{r\.progress\} \/>/);
 assert.match(editor,/<RoutePreview/);
 assert.match(editor,/REQUEST_TIMEOUT_UNKNOWN/);
 assert.match(preview,/\/api\/v1\/requests\/route-preview/);
 assert.match(preview,/silent: true/);
 assert.match(ai,/\/ai-assessments/);
});
test('AI assist suggests another form but never switches it on its own', () => {
 const ai=readFileSync(new URL('../src/components/AiAssist.jsx',import.meta.url),'utf8');
 const classifyHandler=ai.slice(ai.indexOf('/api/v1/ai/classify'),ai.indexOf('/api/v1/ai/risk-score'));
 assert.doesNotMatch(classifyHandler,/onSuggestType/);
 assert.match(ai,/Chuyển sang biểu mẫu này/);
 assert.doesNotMatch(ai,/type === "EQUIPMENT" \? 3 : 2/);
});
test('user form lets admins set the direct manager, excluding the edited user', () => {
 const page=readFileSync(new URL('../src/components/UserManagementPage.jsx',import.meta.url),'utf8');
 assert.match(page,/Người quản lý trực tiếp/);
 assert.match(page,/manager_id: u\.manager_id \|\| ""/);
 assert.match(page,/m\.id !== editUserModal\?\.id/);
});
test('an incomplete draft can be saved; sending still enforces required fields', () => {
 const editor=readFileSync(new URL('../src/components/RequestEditor.jsx',import.meta.url),'utf8');
 const draftBtn=editor.slice(editor.indexOf('value="draft"')-200, editor.indexOf('Lưu bản nháp'));
 assert.match(draftBtn,/formNoValidate/);
 const sendBtn=editor.slice(editor.indexOf('value="send"')-120, editor.indexOf('value="send"')+200);
 assert.doesNotMatch(sendBtn,/formNoValidate/);
});
