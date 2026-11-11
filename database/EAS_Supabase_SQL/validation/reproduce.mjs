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
 const results=await db.exec(await load('03_database_regression_DEV_ONLY.sql'));
 const cases=results.flatMap(r=>r.rows??[]).filter(r=>r.database_test?.startsWith('PASS'));
 const counts=(await db.query('SELECT (SELECT count(*) FROM eas.request) AS requests,(SELECT count(*) FROM eas.app_user) AS users')).rows[0];
 if(counts.requests!==0||counts.users!==0)throw Error('Regression fixture transaction did not roll back');
 await db.exec(await load('../migrations/04_current_schema_upgrade.sql'));
 await db.exec(`INSERT INTO eas.department(id,code,name)
   VALUES('00000005-0000-4000-8000-000000000001','UPGRADE_TEST','Upgrade Test');
   INSERT INTO eas.app_user(id,email,display_name,department_id,password_hash,must_change_password)
   VALUES('00000006-0000-4000-8000-000000000001','upgrade.user@eas.com','Upgrade Test',
     '00000005-0000-4000-8000-000000000001','!UNUSABLE_UPGRADE_TEST',true);`);
 const emailCheck=(await db.query(`SELECT conname FROM pg_constraint
   WHERE conrelid='eas.app_user'::regclass AND contype='c'
     AND pg_get_constraintdef(oid) ILIKE '%email%' LIMIT 1`)).rows[0]?.conname;
 if(!emailCheck)throw Error('Could not locate baseline email constraint for legacy upgrade fixture');
 await db.exec(`ALTER TABLE eas.app_user DROP CONSTRAINT "${emailCheck.replaceAll('"','""')}";
   ALTER TABLE eas.app_user RENAME COLUMN email TO username;
   ALTER TABLE eas.app_user RENAME CONSTRAINT app_user_email_key TO app_user_username_key;
   ALTER TABLE eas.app_user ADD CONSTRAINT app_user_username_check
     CHECK (username=lower(btrim(username)) AND length(username)>0);`);
 await db.exec(await load('../migrations/05_email_login_and_password_reset.sql'));
 await db.exec(await load('02_verify_installation_READ_ONLY.sql'));
 const preserved=(await db.query(`SELECT email,auth_version FROM eas.app_user
   WHERE id='00000006-0000-4000-8000-000000000001'`)).rows[0];
 if(preserved?.email!=='upgrade.user@eas.com'||preserved.auth_version!==1)
   throw Error('Upgrade did not preserve the account and normalize/invalidate its legacy credentials');
 await db.exec(`DELETE FROM eas.app_user WHERE id='00000006-0000-4000-8000-000000000001';
   DELETE FROM eas.department WHERE id='00000005-0000-4000-8000-000000000001';`);
 await db.exec(await load('01_demo_seed_DEV_ONLY.sql'));
 await db.exec(await load('02_verify_installation_READ_ONLY.sql'));
 try{await db.exec(await load('00_eas_supabase_schema.sql'));throw Error('Installer failed to reject rerun');}
 catch(e){if(!e.message.includes('Schema eas already exists'))throw e;await db.exec('ROLLBACK;');}
 if((await db.query('SELECT count(*) AS n FROM eas.app_user')).rows[0].n!==10)throw Error('Rerun changed seeded data');
 const gmailMigration=(await load('../migrations/06_dev_gmail_aliases.sql'))
   .replace('REPLACE_WITH_YOUR_GMAIL_ADDRESS','integrationtest@gmail.com');
 await db.exec(gmailMigration);
 await db.exec(await load('02_verify_installation_READ_ONLY.sql'));
 const gmailAliasState=(await db.query(`SELECT count(*) AS n,
   count(*) FILTER (WHERE email ~ '@gmail[.]com$') AS gmail,
   count(*) FILTER (WHERE auth_version>=1) AS versioned
   FROM eas.app_user`)).rows[0];
 if(gmailAliasState.n!==10||gmailAliasState.gmail!==10||gmailAliasState.versioned!==10)
   throw Error(`Unexpected Gmail alias state: ${JSON.stringify(gmailAliasState)}`);
 const upgraded=(await db.query(`SELECT
   (SELECT count(*) FROM eas.request_type) AS request_types,
   (SELECT count(*) FROM eas.lifecycle) AS lifecycles,
   (SELECT count(*) FROM eas.role) AS roles,
   (SELECT count(*) FROM eas.password_reset_request) AS reset_requests,
   (SELECT count(*) FROM eas.app_user WHERE email !~ '^[^@[:space:]]+@(eas|gmail)[.]com$') AS invalid_emails`)).rows[0];
 if(upgraded.request_types!==10||upgraded.lifecycles!==3||upgraded.roles!==7||upgraded.reset_requests!==0||upgraded.invalid_emails!==0)throw Error('Database upgrade migrations produced an unexpected schema or data state');
 const vectors=JSON.parse(await load('demo_canonical_hash_vectors.json'));
 for(const v of vectors.admin_events)if(createHash('sha256').update(v.canonical_utf8).digest('hex')!==v.sha256)throw Error('Audit seed hash mismatch');
 for(const v of vectors.config_releases)if(createHash('sha256').update(v.canonical_content).digest('hex')!==v.content_sha256)throw Error('Config seed hash mismatch');
 console.log(JSON.stringify({result:'PASS',engine,sql_assertions:cases.length,checks:['fresh install','baseline regression SQL','catalog upgrade','legacy username migration preserves accounts and invalidates sessions','password-reset schema and grants','read-only verification','fixture rollback','standalone demo seed','read-only verification after seed','installer refuses rerun without mutation','test-only Gmail alias migration invalidates sessions','read-only verification after Gmail migration','seed SHA256 vectors'],limits:'One PostgreSQL WASM backend; no actual Supabase project, external services, concurrency or application acceptance tests.'},null,2));
}catch(e){console.error(JSON.stringify({result:'FAIL',message:e.message,sqlstate:e.code,detail:e.detail},null,2));process.exitCode=1;}
finally{await db.close();}
