// npm install && npm test, from this directory. Uses an ephemeral PostgreSQL WASM database.
// Does not connect to Supabase or touch a project database.
import {PGlite} from '@electric-sql/pglite';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const db=new PGlite();
const load=async name=>readFile(new URL('../'+name,import.meta.url),'utf8');
try{
 const engine=(await db.query('SELECT version() AS engine')).rows[0].engine;
 await db.exec('CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS;');
 await db.exec(await load('00_eas_supabase_schema.sql'));
 await db.exec(await load('02_verify_installation_READ_ONLY.sql'));
 const results=await db.exec(await load('03_database_regression_DEV_ONLY.sql'));
 const cases=results.flatMap(r=>r.rows??[]).filter(r=>r.database_test?.startsWith('PASS'));
 const counts=(await db.query('SELECT (SELECT count(*) FROM eas.request) AS requests,(SELECT count(*) FROM eas.app_user) AS users')).rows[0];
 if(counts.requests!==0||counts.users!==0)throw Error('Regression fixture transaction did not roll back');
 await db.exec(await load('01_demo_seed_DEV_ONLY.sql'));
 await db.exec(await load('02_verify_installation_READ_ONLY.sql'));
 try{await db.exec(await load('00_eas_supabase_schema.sql'));throw Error('Installer failed to reject rerun');}
 catch(e){if(!e.message.includes('Schema eas already exists'))throw e;await db.exec('ROLLBACK;');}
 if((await db.query('SELECT count(*) AS n FROM eas.app_user')).rows[0].n!==10)throw Error('Rerun changed seeded data');
 const vectors=JSON.parse(await load('demo_canonical_hash_vectors.json'));
 for(const v of vectors.admin_events)if(createHash('sha256').update(v.canonical_utf8).digest('hex')!==v.sha256)throw Error('Audit seed hash mismatch');
 for(const v of vectors.config_releases)if(createHash('sha256').update(v.canonical_content).digest('hex')!==v.content_sha256)throw Error('Config seed hash mismatch');
 console.log(JSON.stringify({result:'PASS',engine,sql_assertions:cases.length,checks:['fresh install','read-only verification','regression SQL','fixture rollback','standalone demo seed','read-only verification after seed','installer refuses rerun without mutation','seed SHA256 vectors'],limits:'One PostgreSQL WASM backend; no actual Supabase project, external services, concurrency or application acceptance tests.'},null,2));
}catch(e){console.error(JSON.stringify({result:'FAIL',message:e.message,sqlstate:e.code,detail:e.detail},null,2));process.exitCode=1;}
finally{await db.close();}
