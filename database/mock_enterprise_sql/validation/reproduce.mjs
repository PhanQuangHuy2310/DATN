// Uses the dependency already pinned by EAS_Supabase_SQL/validation.
// Runs entirely in an ephemeral PostgreSQL WASM database.
import {PGlite} from '../../EAS_Supabase_SQL/validation/node_modules/@electric-sql/pglite/dist/index.js';
import {readFile} from 'node:fs/promises';

const db = new PGlite();
const loadHere = async name => readFile(new URL('../' + name, import.meta.url), 'utf8');
const loadBase = async name => readFile(new URL('../../EAS_Supabase_SQL/' + name, import.meta.url), 'utf8');

try {
  await db.exec('CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS;');
  await db.exec(await loadBase('00_eas_supabase_schema.sql'));
  await db.exec(await loadHere('00_mock_enterprise_schemas.sql'));
  await db.exec(await loadHere('01_mock_seed_DEV_ONLY.sql'));
  const verification = await db.exec(await loadHere('02_verify_READ_ONLY.sql'));
  const defects = verification.flatMap(result => result.rows ?? []);
  if (defects.length) throw new Error(`Verification defects: ${JSON.stringify(defects)}`);

  const counts = (await db.query(`
    SELECT
      (SELECT count(*)::int FROM mock_hr.employee) employees,
      (SELECT count(*)::int FROM mock_assets.asset) assets,
      (SELECT count(*)::int FROM mock_facilities.resource) facilities,
      (SELECT count(*)::int FROM mock_crm.customer) customers,
      (SELECT count(*)::int FROM mock_procurement.supplier) suppliers,
      (SELECT count(*)::int FROM mock_it.application) applications,
      (SELECT count(*)::int FROM mock_finance.expense_category) expense_categories,
      (SELECT count(*)::int FROM mock_travel.travel_option) travel_options
  `)).rows[0];
  if (Object.values(counts).some(value => value < 2)) throw new Error(`Insufficient fixtures: ${JSON.stringify(counts)}`);

  try {
    await db.exec("INSERT INTO mock_assets.asset_loan(id,asset_id,borrower_employee_id,starts_at,due_at,status) VALUES ('32000000-0000-4000-8000-000000000002','31000000-0000-4000-8000-000000000002','20000000-0000-4000-8000-000000000003',now(),now()+interval '1 day','ACTIVE')");
    throw new Error('Open-loan uniqueness constraint was bypassed');
  } catch (error) {
    if (!String(error.message).includes('asset loan overlaps')) throw error;
    await db.exec('ROLLBACK;');
  }

  console.log(JSON.stringify({result: 'PASS', counts, checks: ['fresh install', 'synthetic seed', 'read-only verification', 'open-loan concurrency invariant'], limits: 'Single PostgreSQL WASM backend; no Supabase deployment or multi-session concurrency.'}, null, 2));
} catch (error) {
  console.error(JSON.stringify({result: 'FAIL', message: error.message, sqlstate: error.code, detail: error.detail}, null, 2));
  process.exitCode = 1;
} finally {
  await db.close();
}
