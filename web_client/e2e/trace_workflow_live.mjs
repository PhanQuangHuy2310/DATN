/**
 * EAS GUIDED LIVE E2E — instrument real user workflows without changing backend.
 * No mocked endpoints; no secrets read, logged or stored.
 * Requires explicit EAS_E2E_TEST_ENV=YES because the human operator may mutate data.
 * Example (Windows CMD):
 *   set EAS_E2E_TEST_ENV=YES
 *   cd web_client
 *   node e2e/trace_workflow_live.mjs
 */
import { chromium } from '@playwright/test';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';
import fs from 'node:fs/promises';
import path from 'node:path';

const CLIENT_URL = process.env.EAS_E2E_CLIENT_URL || 'http://127.0.0.1:5173';
const ADMIN_URL = process.env.EAS_E2E_ADMIN_URL || 'http://127.0.0.1:8081';
const SLOW_MS = Math.max(500, Number(process.env.EAS_E2E_SLOW_MS || '2500'));
const FLOW = process.env.EAS_E2E_FLOW || 'complete';
const flows = {
  complete: [
    ['E2E-01', 'REQUESTER đăng nhập', 'Mở cổng nhân viên. Đăng nhập tài khoản REQUESTER; kiểm tra dashboard và menu theo vai trò.'],
    ['E2E-02', 'Chọn danh mục và tạo nháp', 'Mở Tạo yêu cầu, chọn mẫu thuộc vòng đời C; điền dữ liệu hợp lệ và Lưu nháp.'],
    ['E2E-03', 'Cập nhật nháp, tệp và tải lại', 'Sửa nháp, đính kèm tệp test được phép; mở lại để kiểm tra dữ liệu vẫn lưu.'],
    ['E2E-04', 'Gửi phê duyệt', 'Gửi hồ sơ; ghi mã hồ sơ và kiểm tra trạng thái, tuyến duyệt, bước người phụ trách.'],
    ['E2E-05', 'REQUESTER xem timeline / thông báo', 'Mở hồ sơ vừa gửi, kiểm tra lịch sử, thông báo, không thấy nút phê duyệt của APPROVER.'],
    ['E2E-06', 'APPROVER đăng nhập và mở hàng chờ', 'Đăng xuất REQUESTER, đăng nhập APPROVER; mở thông báo / danh sách chờ duyệt, truy cập hồ sơ.'],
    ['E2E-07', 'APPROVER phê duyệt từng cấp', 'Duyệt theo đúng quy tắc và đúng người được giao. Nếu nhiều cấp, đổi tài khoản và duyệt từng cấp.'],
    ['E2E-08', 'EXECUTOR nhận và bắt đầu việc', 'Đăng xuất, đăng nhập EXECUTOR hợp lệ; tìm hồ sơ và bấm Nhận/Bắt đầu thực thi.'],
    ['E2E-09', 'EXECUTOR gửi kết quả', 'Cập nhật tiến độ, đính kèm bằng chứng theo mẫu, nộp hoàn thành thực thi.'],
    ['E2E-10', 'ACCEPTOR nghiệm thu', 'Đăng nhập ACCEPTOR được phân công; mở hồ sơ, xem bằng chứng, nghiệm thu thành công.'],
    ['E2E-11', 'REQUESTER xác nhận hoàn tất', 'Đăng nhập lại REQUESTER; kiểm tra trạng thái cuối, timeline, thông báo và bằng chứng.'],
    ['E2E-12', 'AUDITOR kiểm tra lịch sử', 'Đăng nhập AUDITOR; kiểm tra chỉ đọc, danh sách quyết định, người thao tác, thời điểm và audit.'],
  ],
  reject: [
    ['E2E-R01', 'Tạo hồ sơ và gửi phê duyệt', 'Đăng nhập REQUESTER; tạo một hồ sơ thử và gửi thành công.'],
    ['E2E-R02', 'APPROVER từ chối', 'Đăng nhập APPROVER đúng bước và từ chối, nhập lý do bắt buộc.'],
    ['E2E-R03', 'REQUESTER kiểm tra kết quả', 'Đăng nhập REQUESTER, kiểm tra trạng thái REJECTED, lý do, timeline, thông báo.'],
    ['E2E-R04', 'Kiểm tra quyền sau từ chối', 'Bảo đảm không xuất hiện thao tác thực thi/nghiệm thu trái luồng; hồ sơ không bị duyệt lần nữa.'],
  ],
  revise: [
    ['E2E-N01', 'Tạo và gửi hồ sơ', 'REQUESTER tạo hồ sơ thử hợp lệ và gửi phê duyệt.'],
    ['E2E-N02', 'APPROVER yêu cầu bổ sung', 'APPROVER bấm Yêu cầu bổ sung (NEEDS_INFO), nhập lý do.'],
    ['E2E-N03', 'REQUESTER sửa và gửi lại', 'REQUESTER thấy lý do, sửa nội dung, gửi lại và kiểm tra revision mới.'],
    ['E2E-N04', 'APPROVER duyệt phiên mới', 'APPROVER duyệt revision mới, không dùng nhầm nội dung revision cũ.'],
  ],
  resilience: [
    ['E2E-F01', 'Đăng nhập bình thường', 'Đăng nhập một tài khoản thử, mở trang hồ sơ và quan sát Network.'],
    ['E2E-F02', 'Redis mất kết nối (có kiểm soát)', 'Trên TEST env, dừng Redis có kiểm soát; tải lại dữ liệu; ghi UI và lỗi API. Chỉ làm khi bảo đảm không ảnh hưởng người khác.'],
    ['E2E-F03', 'Khôi phục Redis', 'Khởi động Redis; kiểm tra app khôi phục mà không gọi API dồn dập.'],
    ['E2E-F04', 'Thử lại sau 429', 'Nếu xuất hiện 429 tự nhiên, kiểm tra Retry-After, không spam nút; tránh cố tình gửi quá nhiều request.'],
    ['E2E-F05', 'Phiên hết hạn', 'Trong môi trường TEST, đợi phiên hết hạn và kiểm tra trang đăng nhập cùng hành vi bảo vệ dữ liệu.'],
  ],
};
if (!flows[FLOW]) {
  console.error('Invalid EAS_E2E_FLOW. Supported: ' + Object.keys(flows).join(', '));
  process.exit(2);
}
if (process.env.EAS_E2E_TEST_ENV !== 'YES') {
  console.error('CHỈ CHẠY trên môi trường test. Đặt EAS_E2E_TEST_ENV=YES sau khi đã xác nhận dữ liệu thử được phép tạo/sửa.');
  process.exit(2);
}

const stamp = new Date().toISOString().replaceAll(/[:.]/g, '-');
const outDir = path.resolve(process.env.EAS_E2E_OUTPUT || `test-results/eas-e2e-${FLOW}-${stamp}`);
await fs.mkdir(outDir, { recursive: true });
const steps = flows[FLOW];
const events = [];
const stages = [];
const requestStarts = new WeakMap();
const perEndpoint = new Map();
let activeStage = 'BOOT';
const redact = (text = '') => String(text)
  .replace(/https?:\/\/[^\s"'<>]+/gi, (candidate) => {
    try { const u = new URL(candidate); return u.origin + u.pathname; } catch { return '[URL]'; }
  })
  .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[email]')
  .replace(/(bearer\s+)[^\s]+/gi, '$1[REDACTED]')
  .slice(0, 300);
const escape = (value = '') => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const labelUrl = (raw) => { try { const u = new URL(raw); return `${u.pathname}`; } catch { return '[invalid URL]'; }};
const add = (type, severity, details = {}) => {
  events.push({ stage: activeStage, time: new Date().toISOString(), type, severity, ...details });
  if (severity === 'FAIL') console.error(`[${activeStage}] ${type} ${details.method || ''} ${details.path || ''} ${details.status ?? ''} ${details.message || ''}`);
};
const startProbe = async (url) => {
  const target = new URL(url);
  const probe = `${target.origin}/`;
  try {
    const response = await fetch(probe, { signal: AbortSignal.timeout(4000) });
    add('PREFLIGHT', response.ok ? 'OK' : 'WARN', { path: `${target.origin}/`, status: response.status });
  } catch (error) {
    add('PREFLIGHT', 'FAIL', { path: `${target.origin}/`, message: redact(error.message) });
  }
};
const rl = createInterface({ input: stdin, output: stdout });
let browser;
let context;
try {
  console.log('\nEAS GUIDED LIVE E2E — Không mock API, không tự gửi thao tác ghi');
  console.log('CHỈ dùng tài khoản và dữ liệu thử trên DB test; các ảnh màn hình có thể chứa dữ liệu hiện trên UI.');
  console.log(`Client: ${CLIENT_URL} | Admin: ${ADMIN_URL} | Flow: ${FLOW}`);
  console.log('Không lưu username/password, cookie, header xác thực hoặc body API.');
  await startProbe(CLIENT_URL);
  browser = await chromium.launch({ headless: false });
  context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: 'vi-VN', acceptDownloads: true });
  context.on('request', request => requestStarts.set(request, Date.now()));
  context.on('response', response => {
    const request = response.request();
    const url = request.url();
    if (!/\/api\/v1\//.test(url) && !/\/health\//.test(url)) return;
    const pathOnly = labelUrl(url);
    const duration = requestStarts.has(request) ? Date.now() - requestStarts.get(request) : null;
    const status = response.status();
    const headers = response.headers();
    const correlation = headers['x-correlation-id'] || headers['x-request-id'] || '';
    const retry = headers['retry-after'] || '';
    const groupKey = `${request.method()} ${pathOnly}`;
    const agg = perEndpoint.get(groupKey) || { count: 0, failures: 0, slow: 0, totalMs: 0, maxMs: 0 };
    agg.count += 1;
    agg.failures += status >= 400 ? 1 : 0;
    agg.slow += duration !== null && duration >= SLOW_MS ? 1 : 0;
    agg.totalMs += duration || 0;
    agg.maxMs = Math.max(agg.maxMs, duration || 0);
    perEndpoint.set(groupKey, agg);
    if (status >= 400 || duration >= SLOW_MS) {
      add(status >= 500 ? 'HTTP_5XX' : status === 429 ? 'HTTP_429' : status >= 400 ? 'HTTP_4XX' : 'SLOW_API',
        (status >= 500 || status === 429) ? 'FAIL' : status >= 400 ? 'WARN' : 'SLOW',
        { method: request.method(), path: pathOnly, status, durationMs: duration, correlationId: correlation, retryAfter: retry });
    }
  });
  context.on('requestfailed', request => {
    // Navigation cancellations are common when a user switches screens.
    const message = redact(request.failure()?.errorText || 'request failed');
    const intentionalAbort = /ERR_ABORTED|NS_BINDING_ABORTED/.test(message);
    add('REQUEST_FAILED', intentionalAbort ? 'WARN' : 'FAIL', { path: labelUrl(request.url()), method: request.method(), message });
  });
  const pageListener = page => {
    page.on('pageerror', error => add('JS_ERROR', 'FAIL', { message: redact(error.message) }));
    page.on('console', message => {
      if (message.type() === 'error') add('CONSOLE_ERROR', 'WARN', { message: redact(message.text()) });
    });
  };
  context.on('page', pageListener);
  const page = await context.newPage();
  await page.goto(CLIENT_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(e => add('NAVIGATION', 'FAIL', { message: redact(e.message) }));

  for (const [id, title, instructions] of steps) {
    activeStage = id;
    console.log(`\n${id} — ${title}\n${instructions}`);
    console.log('Thao tác trực tiếp trên Chrome đang mở, sau đó trở lại CMD.');
    const before = events.length;
    const answer = (await rl.question('Enter = PASS | f = FAIL | b = BLOCKED | s = SKIP | q = END : ')).trim().toLowerCase();
    if (answer === 'q') break;
    const chosen = ({ f: 'FAIL', b: 'BLOCKED', s: 'SKIP' })[answer] || 'PASS';
    const stageEvents = events.slice(before);
    const serious = stageEvents.some(e => e.severity === 'FAIL');
    const slow = stageEvents.some(e => e.severity === 'SLOW');
    const status = chosen === 'PASS' && serious ? 'CHECK' : chosen;
    let screenshot = '';
    const current = context.pages().filter(p => !p.isClosed()).at(-1);
    if (current) {
      screenshot = `${id}.png`;
      try { await current.screenshot({ path: path.join(outDir, screenshot), timeout: 8000, animations: 'disabled' }); }
      catch (error) { screenshot = ''; add('SCREENSHOT_ERROR', 'WARN', { message: redact(error.message) }); }
    }
    const visibleUrl = current ? labelUrl(current.url()) : '';
    stages.push({ id, title, instructions, operator: chosen, status, screenshot, visibleUrl, notes: `${stageEvents.filter(e=>e.severity==='FAIL').length} lỗi nghiêm trọng; ${stageEvents.filter(e=>e.severity==='SLOW').length} API chậm`, slow });
    console.log(`=> ${status}${serious ? ' (có lỗi HTTP/JS dù đã chọn PASS)' : ''}.`);
  }
} catch (error) {
  add('RUNNER_ERROR', 'FAIL', { message: redact(error.message) });
  console.error(error);
} finally {
  try { await browser?.close(); } catch { /* ignore */ }
  rl.close();
}
const endpoints = [...perEndpoint].map(([key, a]) => ({ endpoint: key, ...a, averageMs: Math.round(a.totalMs / Math.max(a.count, 1)) })).sort((a, b) => b.failures - a.failures || b.maxMs - a.maxMs);
const summary = { runAt: new Date().toISOString(), flow: FLOW, client: CLIENT_URL, admin: ADMIN_URL, steps: stages.length, stages, endpoints, events };
await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(summary, null, 2), 'utf8');
const statusColor = status => ({ PASS:'#047857', FAIL:'#b91c1c', BLOCKED:'#9a6700', CHECK:'#b45309', SKIP:'#64748b' })[status] || '#475569';
const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"/><title>EAS E2E ${escape(FLOW)}</title>
<style>body{font:14px system-ui,sans-serif;background:#f8fafc;color:#17212d;margin:24px auto;max-width:1300px;padding:0 16px}h1{font-size:25px}h2{font-size:18px;margin-top:28px}p{line-height:1.5}table{border-collapse:collapse;width:100%;background:white;table-layout:auto}th,td{border-bottom:1px solid #e2e8f0;padding:9px;text-align:left;vertical-align:top}th{background:#e9eff5;position:sticky;top:0}small{color:#64748b}img{width:180px;max-width:100%;border-radius:6px;border:1px solid #cbd5e1}code{font-size:12px}.scroll{overflow:auto;border:1px solid #e2e8f0;border-radius:8px}strong.status{font-size:12px}header{padding-bottom:12px;border-bottom:1px solid #cbd5e1}</style></head><body>
<header><h1>Báo cáo E2E có ghi nhận lỗi — ${escape(FLOW)}</h1><p>Chạy lúc ${escape(summary.runAt)} · ${stages.length}/${steps.length} bước đã đánh giá · API chậm từ ${SLOW_MS} ms</p><small>Không lưu cookie, mật khẩu, header Authorization hoặc body API. Ảnh có thể chứa dữ liệu trên giao diện — chỉ chia sẻ khi đã kiểm tra.</small></header>
<h2>Chuỗi bước E2E</h2><div class="scroll"><table><thead><tr><th>ID</th><th>Bước thực tế</th><th>Kết quả</th><th>Địa chỉ màn</th><th>Ghi chú</th><th>Ảnh</th></tr></thead><tbody>${stages.map(s=>`<tr><td><b>${escape(s.id)}</b></td><td>${escape(s.title)}<br><small>${escape(s.instructions)}</small></td><td><strong class="status" style="color:${statusColor(s.status)}">${escape(s.status)}</strong></td><td><code>${escape(s.visibleUrl)}</code></td><td>${escape(s.notes)}</td><td>${s.screenshot ? `<a href="${escape(s.screenshot)}"><img src="${escape(s.screenshot)}" loading="lazy"></a>` : ''}</td></tr>`).join('')}</tbody></table></div>
<h2>API có lỗi hoặc phản hồi chậm</h2><div class="scroll"><table><thead><tr><th>Giai đoạn</th><th>Loại</th><th>Request</th><th>HTTP</th><th>Thời gian</th><th>Correlation ID</th><th>Thông tin</th></tr></thead><tbody>${events.filter(e=>e.type!=='PREFLIGHT').map(e=>`<tr><td>${escape(e.stage)}</td><td>${escape(e.type)}</td><td>${escape((e.method||'')+' '+(e.path||''))}</td><td>${escape(e.status??'')}</td><td>${escape(e.durationMs===null || e.durationMs===undefined?'':e.durationMs+' ms')}</td><td><code>${escape(e.correlationId||'')}</code></td><td>${escape(e.message || (e.retryAfter ? 'Retry-After: '+e.retryAfter : ''))}</td></tr>`).join('')}</tbody></table></div>
<h2>Tổng hợp API theo tần suất</h2><div class="scroll"><table><thead><tr><th>API</th><th>Số gọi</th><th>HTTP 4xx/5xx</th><th>Lượt chậm</th><th>TB</th><th>Cao nhất</th></tr></thead><tbody>${endpoints.map(e=>`<tr><td><code>${escape(e.endpoint)}</code></td><td>${e.count}</td><td>${e.failures}</td><td>${e.slow}</td><td>${e.averageMs} ms</td><td>${e.maxMs} ms</td></tr>`).join('')}</tbody></table></div>
<p><small>401 khi chưa đăng nhập hoặc 403 khi cố ý thử quyền có thể là kết quả mong đợi; cần đối chiếu với bước thực thi. CHECK = người kiểm thử chọn PASS nhưng trình duyệt ghi nhận lỗi nghiêm trọng.</small></p></body></html>`;
await fs.writeFile(path.join(outDir, 'report.html'), html, 'utf8');
console.log(`\nBáo cáo: ${path.join(outDir, 'report.html')}`);
console.log('Để chẩn đoán: mở report.html, tra API + HTTP + Correlation ID theo bước lỗi trong terminal Django.');
