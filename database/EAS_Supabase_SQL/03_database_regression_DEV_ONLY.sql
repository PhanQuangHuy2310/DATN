-- DEVELOPMENT ONLY. Fresh 00 schema with no users, releases or requests.

-- All rows roll back. A generated request-code sequence may advance; do not run on production.

BEGIN;

SET LOCAL timezone='UTC';

SET LOCAL ROLE eas_api;

-- Test-only identities and policy. Password hashes are deliberately unusable.
-- No object storage files are created. DEMO_PORTAL/READ_BASIC are fictional.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM eas.app_user) OR EXISTS(SELECT 1 FROM eas.config_release) OR EXISTS(SELECT 1 FROM eas.request) THEN
  RAISE EXCEPTION 'Demo seed requires an empty EAS domain. Never run it on production.';
 END IF;
END $$;
SELECT eas.lock_security(true);
INSERT INTO eas.department(id,code,name) VALUES('00000001-0000-4000-8000-000000000001','DEMO_D01','Demo Business');
INSERT INTO eas.department(id,code,name,parent_id) VALUES('00000001-0000-4000-8000-000000000002','DEMO_D02','Demo Operations','00000001-0000-4000-8000-000000000001');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000001','demo_requester','DEMO REQUESTER','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_REQUESTER',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000002','demo_handover','DEMO HANDOVER','00000001-0000-4000-8000-000000000002','!UNUSABLE_DEMO_HANDOVER',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000003','demo_manager','DEMO MANAGER','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_MANAGER',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000004','demo_finance','DEMO FINANCE','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_FINANCE',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000005','demo_director','DEMO DIRECTOR','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_DIRECTOR',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000006','demo_it','DEMO IT','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_IT',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000007','demo_asset','DEMO ASSET','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_ASSET',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000008','demo_policy_admin','DEMO POLICY_ADMIN','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_POLICY_ADMIN',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000009','demo_auditor','DEMO AUDITOR','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_AUDITOR',true,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.app_user(id,username,display_name,department_id,password_hash,must_change_password,created_at) VALUES('00000002-0000-4000-8000-000000000010','demo_ops_admin','DEMO OPS_ADMIN','00000001-0000-4000-8000-000000000001','!UNUSABLE_DEMO_OPS_ADMIN',true,'2026-01-01T00:00:00.000000Z');
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000003' WHERE id='00000002-0000-4000-8000-000000000001';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000003' WHERE id='00000002-0000-4000-8000-000000000002';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000003';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000004';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000006';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000007';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000008';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000009';
UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000005' WHERE id='00000002-0000-4000-8000-000000000010';
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000001','REQUESTER','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000002','00000002-0000-4000-8000-000000000002','REQUESTER','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','ACCEPTOR','GLOBAL','ONE','00000000-0000-4000-8000-000000000003','2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','ACCEPTOR','GLOBAL','ONE','00000000-0000-4000-8000-000000000003','2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000005','00000002-0000-4000-8000-000000000003','APPROVER','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000006','00000002-0000-4000-8000-000000000004','APPROVER','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000007','00000002-0000-4000-8000-000000000005','APPROVER','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000008','00000002-0000-4000-8000-000000000006','EXECUTOR','GLOBAL','ONE','00000000-0000-4000-8000-000000000002','2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000009','00000002-0000-4000-8000-000000000007','EXECUTOR','GLOBAL','ONE','00000000-0000-4000-8000-000000000003','2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000010','00000002-0000-4000-8000-000000000008','POLICY_ADMIN','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000011','00000002-0000-4000-8000-000000000009','AUDITOR','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
INSERT INTO eas.role_membership(id,user_id,role,scope_kind,type_scope,type_id,valid_from) VALUES('00000004-0000-4000-8000-000000000012','00000002-0000-4000-8000-000000000010','OPS_ADMIN','GLOBAL','ALL',NULL,'2026-01-01T00:00:00.000000Z');
UPDATE eas.security_epoch SET version=version+1,updated_at=clock_timestamp() WHERE id=1;
INSERT INTO eas.admin_event(id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000005-0000-4000-8000-000000000001',1,'00000002-0000-4000-8000-000000000008','HUMAN','DEMO_IDENTITY_IMPORT','identity_import','DEMO_BOOTSTRAP',NULL,NULL,'{"users":10,"departments":2,"memberships":12}'::jsonb,'Development fixtures only; no production authorization.','00000006-0000-4000-8000-000000000001','2026-01-01T00:00:00.000000Z',1,'0000000000000000000000000000000000000000000000000000000000000000','d15fab6942d54502e496f491db4a3f459277f2891da5a58db6d613a66c7faf57');
INSERT INTO eas.config_release(id,type_id,version,state,lifecycle,form_schema,route_rules,actor_bindings,sla_profile,created_by,published_by,created_at,published_at,content_sha256) VALUES('00000003-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001',1,'PUBLISHED','A','{"schema_version":1,"type":"object","properties":{"title":{"type":"string","minLength":5,"maxLength":150},"reason":{"type":"string","minLength":10,"maxLength":2000},"start_date":{"type":"string","format":"date"},"end_date":{"type":"string","format":"date"},"handover_user_id":{"type":"string","format":"uuid"}},"required":["title","reason","start_date","end_date","handover_user_id"],"additionalProperties":false}'::jsonb,'{"schema_version":1,"rules":[{"id":"LEAVE-DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":null,"acceptor":null}'::jsonb,'{"schema_version":1,"departments":{"00000001-0000-4000-8000-000000000001":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"},"00000001-0000-4000-8000-000000000002":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"}}}'::jsonb,'{"schema_version":1,"clock":"CALENDAR_UTC","approval_hours":24,"execution_hours":null,"acceptance_hours":null,"reminder_fraction":0.5}'::jsonb,'00000002-0000-4000-8000-000000000008','00000002-0000-4000-8000-000000000008','2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z','1389c59a24ce11bb5d8e84fa1a2cdc2e97ea3b7470f1a5c0f1fc4c7a5b2e5ae7');
UPDATE eas.request_type SET active_release_id='00000003-0000-4000-8000-000000000001' WHERE id='00000000-0000-4000-8000-000000000001';
INSERT INTO eas.admin_event(id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000005-0000-4000-8000-000000000002',2,'00000002-0000-4000-8000-000000000008','HUMAN','DEMO_RELEASE_PUBLISHED','config_release','00000003-0000-4000-8000-000000000001',NULL,'00000000-0000-4000-8000-000000000001','{"release_id":"00000003-0000-4000-8000-000000000001","content_sha256":"1389c59a24ce11bb5d8e84fa1a2cdc2e97ea3b7470f1a5c0f1fc4c7a5b2e5ae7"}'::jsonb,'Development fixtures only; no production authorization.','00000006-0000-4000-8000-000000000002','2026-01-01T00:00:00.000000Z',1,'d15fab6942d54502e496f491db4a3f459277f2891da5a58db6d613a66c7faf57','2354cfe655104c3ab93faea2102fba66499b76b61f4fcb4eb3e4165ccb45c846');
INSERT INTO eas.config_release(id,type_id,version,state,lifecycle,form_schema,route_rules,actor_bindings,sla_profile,created_by,published_by,created_at,published_at,content_sha256) VALUES('00000003-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002',1,'PUBLISHED','B','{"schema_version":1,"type":"object","properties":{"title":{"type":"string","minLength":5,"maxLength":150},"reason":{"type":"string","minLength":10,"maxLength":2000},"app_code":{"type":"string","enum":["DEMO_PORTAL"]},"requested_role":{"type":"string","enum":["READ_BASIC"]},"duration_days":{"type":"integer","minimum":1,"maximum":90},"purpose":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","reason","app_code","requested_role","duration_days","purpose"],"additionalProperties":false}'::jsonb,'{"schema_version":1,"rules":[{"id":"ACCESS-DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":"EXECUTOR_IT","acceptor":null}'::jsonb,'{"schema_version":1,"departments":{"00000001-0000-4000-8000-000000000001":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"},"00000001-0000-4000-8000-000000000002":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"}}}'::jsonb,'{"schema_version":1,"clock":"CALENDAR_UTC","approval_hours":24,"execution_hours":12,"acceptance_hours":null,"reminder_fraction":0.5}'::jsonb,'00000002-0000-4000-8000-000000000008','00000002-0000-4000-8000-000000000008','2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z','534ffd8b5053ba4ad73434a2c12d7736047e834b28a21490ad5b88916c50ff83');
UPDATE eas.request_type SET active_release_id='00000003-0000-4000-8000-000000000002' WHERE id='00000000-0000-4000-8000-000000000002';
INSERT INTO eas.admin_event(id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000005-0000-4000-8000-000000000003',3,'00000002-0000-4000-8000-000000000008','HUMAN','DEMO_RELEASE_PUBLISHED','config_release','00000003-0000-4000-8000-000000000002',NULL,'00000000-0000-4000-8000-000000000002','{"release_id":"00000003-0000-4000-8000-000000000002","content_sha256":"534ffd8b5053ba4ad73434a2c12d7736047e834b28a21490ad5b88916c50ff83"}'::jsonb,'Development fixtures only; no production authorization.','00000006-0000-4000-8000-000000000003','2026-01-01T00:00:00.000000Z',1,'2354cfe655104c3ab93faea2102fba66499b76b61f4fcb4eb3e4165ccb45c846','3a258765da4fd2f54cc135640b7f0bf0aaee4b0ed4e803ce1774132f57dcb711');
INSERT INTO eas.config_release(id,type_id,version,state,lifecycle,form_schema,route_rules,actor_bindings,sla_profile,created_by,published_by,created_at,published_at,content_sha256) VALUES('00000003-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000003',1,'PUBLISHED','C','{"schema_version":1,"type":"object","properties":{"title":{"type":"string","minLength":5,"maxLength":150},"reason":{"type":"string","minLength":10,"maxLength":2000},"item_name":{"type":"string","minLength":2,"maxLength":150},"quantity":{"type":"integer","minimum":1,"maximum":100},"amount_vnd":{"type":"integer","minimum":1,"maximum":1000000000000},"specs":{"type":"string","minLength":10,"maxLength":2000},"location":{"type":"string","minLength":2,"maxLength":200}},"required":["title","reason","item_name","quantity","amount_vnd","specs","location"],"additionalProperties":false}'::jsonb,'{"schema_version":1,"rules":[{"id":"EQ-HIGH","priority":10,"when":{"amount_gt":50000000},"approvers":["DIRECT_MANAGER","FINANCE","DIRECTOR"]},{"id":"EQ-MID","priority":20,"when":{"amount_gte":10000000},"approvers":["DIRECT_MANAGER","FINANCE"]},{"id":"EQ-DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":"EXECUTOR_ASSET","acceptor":"REQUESTER"}'::jsonb,'{"schema_version":1,"departments":{"00000001-0000-4000-8000-000000000001":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"},"00000001-0000-4000-8000-000000000002":{"FINANCE":"00000002-0000-4000-8000-000000000004","DIRECTOR":"00000002-0000-4000-8000-000000000005","EXECUTOR_IT":"00000002-0000-4000-8000-000000000006","EXECUTOR_ASSET":"00000002-0000-4000-8000-000000000007"}}}'::jsonb,'{"schema_version":1,"clock":"CALENDAR_UTC","approval_hours":24,"execution_hours":48,"acceptance_hours":24,"reminder_fraction":0.5}'::jsonb,'00000002-0000-4000-8000-000000000008','00000002-0000-4000-8000-000000000008','2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z','6679b07bdd6f6a9b9052ebc6ad88e3206c3d883d3544754a53be16bfc4c7f7cd');
UPDATE eas.request_type SET active_release_id='00000003-0000-4000-8000-000000000003' WHERE id='00000000-0000-4000-8000-000000000003';
INSERT INTO eas.admin_event(id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000005-0000-4000-8000-000000000004',4,'00000002-0000-4000-8000-000000000008','HUMAN','DEMO_RELEASE_PUBLISHED','config_release','00000003-0000-4000-8000-000000000003',NULL,'00000000-0000-4000-8000-000000000003','{"release_id":"00000003-0000-4000-8000-000000000003","content_sha256":"6679b07bdd6f6a9b9052ebc6ad88e3206c3d883d3544754a53be16bfc4c7f7cd"}'::jsonb,'Development fixtures only; no production authorization.','00000006-0000-4000-8000-000000000004','2026-01-01T00:00:00.000000Z',1,'3a258765da4fd2f54cc135640b7f0bf0aaee4b0ed4e803ce1774132f57dcb711','9ee4920888eea5d079ea8f73a8348aac7f352f229c6305bcee8986fcd0b29527');


DO $test$ BEGIN IF NOT coalesce(((SELECT count(*)=3 FROM eas.request_type WHERE active_release_id IS NOT NULL) AND (SELECT count(*)=10 AND bool_and(password_hash LIKE '!%') FROM eas.app_user)),false) THEN RAISE EXCEPTION 'FAIL Bootstrap has 3 active demo releases and 10 unusable demo accounts'; END IF; END $test$;
SELECT 'PASS Bootstrap has 3 active demo releases and 10 unusable demo accounts' AS database_test;

DO $test$ BEGIN IF NOT coalesce(((SELECT count(*)=30 AND bool_and(relrowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='eas' AND c.relkind='r')),false) THEN RAISE EXCEPTION 'FAIL All 30 tables have RLS enabled'; END IF; END $test$;
SELECT 'PASS All 30 tables have RLS enabled' AS database_test;

DO $test$ BEGIN IF NOT coalesce((NOT has_table_privilege('eas_api','eas.audit_head','UPDATE')),false) THEN RAISE EXCEPTION 'FAIL API cannot rewrite audit head directly'; END IF; END $test$;
SELECT 'PASS API cannot rewrite audit head directly' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.role_membership(user_id,role,scope_kind,type_scope,valid_from) SELECT user_id,role,scope_kind,type_scope,valid_from FROM eas.role_membership WHERE id='00000004-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: NULL-scoped duplicate membership rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS NULL-scoped duplicate membership rejected [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.role_membership(user_id,role,scope_kind,department_id,type_scope) VALUES('00000002-0000-4000-8000-000000000001','REQUESTER','GLOBAL','00000001-0000-4000-8000-000000000001','ALL');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: GLOBAL membership with department rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS GLOBAL membership with department rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.role_membership(user_id,role,scope_kind,type_scope,valid_from,valid_to) VALUES('00000002-0000-4000-8000-000000000001','REQUESTER','GLOBAL','ALL','2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Role date interval rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Role date interval rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.department SET parent_id='00000001-0000-4000-8000-000000000002' WHERE id='00000001-0000-4000-8000-000000000001'; SET CONSTRAINTS ALL IMMEDIATE;$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Department cycle detected at deferred check';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Department cycle detected at deferred check [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.app_user SET manager_id='00000002-0000-4000-8000-000000000001' WHERE id='00000002-0000-4000-8000-000000000003'; SET CONSTRAINTS ALL IMMEDIATE;$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Manager cycle detected at deferred check';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Manager cycle detected at deferred check [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.config_release SET form_schema='{}' WHERE id='00000003-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Published release immutable';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Published release immutable [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request_type SET active_release_id='00000003-0000-4000-8000-000000000002' WHERE id='00000000-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Active release cannot cross request type';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Active release cannot cross request type [23514]' AS database_test;

INSERT INTO eas.request(id,code,requester_id,type_id,draft_release_id) VALUES('0000000a-0000-4000-8000-000000000004','DBTEST-OTHER','00000002-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000001','00000003-0000-4000-8000-000000000001');

INSERT INTO eas.request(id,code,requester_id,type_id,draft_release_id) VALUES('0000000a-0000-4000-8000-000000000005','DBTEST-CANCEL','00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','00000003-0000-4000-8000-000000000001');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request(requester_id,type_id,status) VALUES('00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','FAKE');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Unknown request status rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Unknown request status rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request(requester_id,type_id,draft_release_id) VALUES('00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','00000003-0000-4000-8000-000000000002');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Draft release must match type';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Draft release must match type [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request(requester_id,type_id,origin_request_id) VALUES('00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000004');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Origin owner cannot differ';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Origin owner cannot differ [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request(requester_id,type_id,draft_amount_vnd) VALUES('00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001',1);$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Money must not be placed on leave';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Money must not be placed on leave [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request(requester_id,type_id,draft_amount_vnd) VALUES('00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000003',1000000000001);$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Money upper bound enforced';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Money upper bound enforced [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request SET draft_payload='{"title":"changed"}' WHERE id='0000000a-0000-4000-8000-000000000005'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Version increment required';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Version increment required [23514]' AS database_test;

UPDATE eas.request SET status='CANCELLED',lock_version=1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000005';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request SET status='DRAFT',lock_version=2,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000005'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Terminal request cannot reopen';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Terminal request cannot reopen [23514]' AS database_test;

INSERT INTO eas.request(id,code,requester_id,type_id,draft_release_id,draft_payload,draft_amount_vnd) VALUES('0000000a-0000-4000-8000-000000000001','DBTEST-A','00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','00000003-0000-4000-8000-000000000001','{"title":"Demo leave request","reason":"Personal leave for demonstration","start_date":"2026-12-01","end_date":"2026-12-02","handover_user_id":"00000002-0000-4000-8000-000000000002"}'::jsonb,NULL);

INSERT INTO eas.request_revision(id,request_id,revision_no,release_id,department_id,payload,amount_vnd,submitted_by,payload_sha256) VALUES('0000000b-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001',1,'00000003-0000-4000-8000-000000000001','00000001-0000-4000-8000-000000000001','{"title":"Demo leave request","reason":"Personal leave for demonstration","start_date":"2026-12-01","end_date":"2026-12-02","handover_user_id":"00000002-0000-4000-8000-000000000002"}'::jsonb,NULL,'00000002-0000-4000-8000-000000000001','09d75caa5d7747a5da6ee81fbf72c5cf08bf2d0144c1c140f570af093e4cd022');

INSERT INTO eas.workflow_instance(id,request_id,revision_id,matched_rule_id,resolved_route,lifecycle,planned_executor_id,acceptor_id) VALUES('0000000c-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','0000000b-0000-4000-8000-000000000001','LEAVE-DEFAULT','[{"step_no":1,"assignee_id":"00000002-0000-4000-8000-000000000003","resolver":"DIRECT_MANAGER"}]'::jsonb,'A',NULL,NULL);

INSERT INTO eas.approval_step(id,request_id,instance_id,step_no,assignee_id,state,activated_at) VALUES('0000000d-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','0000000c-0000-4000-8000-000000000001',1,'00000002-0000-4000-8000-000000000003','ACTIVE','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000001','REQUESTER');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','APPROVER');

UPDATE eas.request SET current_revision_id='0000000b-0000-4000-8000-000000000001',status='PENDING_APPROVAL',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000001';

INSERT INTO eas.request(id,code,requester_id,type_id,draft_release_id,draft_payload,draft_amount_vnd) VALUES('0000000a-0000-4000-8000-000000000002','DBTEST-B','00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002','00000003-0000-4000-8000-000000000002','{"title":"Demo access request","reason":"Business need for demonstration","app_code":"DEMO_PORTAL","requested_role":"READ_BASIC","duration_days":30,"purpose":"Read demonstration data only"}'::jsonb,NULL);

INSERT INTO eas.request_revision(id,request_id,revision_no,release_id,department_id,payload,amount_vnd,submitted_by,payload_sha256) VALUES('0000000b-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002',1,'00000003-0000-4000-8000-000000000002','00000001-0000-4000-8000-000000000001','{"title":"Demo access request","reason":"Business need for demonstration","app_code":"DEMO_PORTAL","requested_role":"READ_BASIC","duration_days":30,"purpose":"Read demonstration data only"}'::jsonb,NULL,'00000002-0000-4000-8000-000000000001','f98e828fd0e7eee3af53c237d0830579ec8996ed59fd6740b4f2bfcf9d479922');

INSERT INTO eas.workflow_instance(id,request_id,revision_id,matched_rule_id,resolved_route,lifecycle,planned_executor_id,acceptor_id) VALUES('0000000c-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002','0000000b-0000-4000-8000-000000000002','ACCESS-DEFAULT','[{"step_no":1,"assignee_id":"00000002-0000-4000-8000-000000000003","resolver":"DIRECT_MANAGER"}]'::jsonb,'B','00000002-0000-4000-8000-000000000006',NULL);

INSERT INTO eas.approval_step(id,request_id,instance_id,step_no,assignee_id,state,activated_at) VALUES('0000000d-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002','0000000c-0000-4000-8000-000000000002',1,'00000002-0000-4000-8000-000000000003','ACTIVE','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000002','00000002-0000-4000-8000-000000000001','REQUESTER');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000002','00000002-0000-4000-8000-000000000003','APPROVER');

UPDATE eas.request SET current_revision_id='0000000b-0000-4000-8000-000000000002',status='PENDING_APPROVAL',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000002';

INSERT INTO eas.request(id,code,requester_id,type_id,draft_release_id,draft_payload,draft_amount_vnd) VALUES('0000000a-0000-4000-8000-000000000003','DBTEST-C','00000002-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000003','00000003-0000-4000-8000-000000000003','{"title":"Demo equipment request","reason":"Equipment for demonstration","item_name":"Demo laptop","quantity":1,"amount_vnd":5000000,"specs":"Development fixture specification","location":"Demo office"}'::jsonb,5000000);

INSERT INTO eas.request_revision(id,request_id,revision_no,release_id,department_id,payload,amount_vnd,submitted_by,payload_sha256) VALUES('0000000b-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003',1,'00000003-0000-4000-8000-000000000003','00000001-0000-4000-8000-000000000001','{"title":"Demo equipment request","reason":"Equipment for demonstration","item_name":"Demo laptop","quantity":1,"amount_vnd":5000000,"specs":"Development fixture specification","location":"Demo office"}'::jsonb,5000000,'00000002-0000-4000-8000-000000000001','ca122f8675d740abaef34e5ce4148c062a86a40e1dae61e473f03f138da6f263');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','test-only/no-object/0000000f-0000-4000-8000-000000000001','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.revision_attachment(revision_id,attachment_id,request_id) VALUES('0000000b-0000-4000-8000-000000000003','0000000f-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000003');

INSERT INTO eas.workflow_instance(id,request_id,revision_id,matched_rule_id,resolved_route,lifecycle,planned_executor_id,acceptor_id) VALUES('0000000c-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003','0000000b-0000-4000-8000-000000000003','EQ-DEFAULT','[{"step_no":1,"assignee_id":"00000002-0000-4000-8000-000000000003","resolver":"DIRECT_MANAGER"}]'::jsonb,'C','00000002-0000-4000-8000-000000000007','00000002-0000-4000-8000-000000000001');

INSERT INTO eas.approval_step(id,request_id,instance_id,step_no,assignee_id,state,activated_at) VALUES('0000000d-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003','0000000c-0000-4000-8000-000000000003',1,'00000002-0000-4000-8000-000000000003','ACTIVE','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','REQUESTER');

INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES('0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000003','APPROVER');

UPDATE eas.request SET current_revision_id='0000000b-0000-4000-8000-000000000003',status='PENDING_APPROVAL',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

SET CONSTRAINTS ALL IMMEDIATE; SET CONSTRAINTS ALL DEFERRED;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.request_revision(request_id,revision_no,release_id,department_id,payload,submitted_by,payload_sha256) VALUES('0000000a-0000-4000-8000-000000000004',1,'00000003-0000-4000-8000-000000000002','00000001-0000-4000-8000-000000000002','{}'::jsonb,'00000002-0000-4000-8000-000000000002','0000000000000000000000000000000000000000000000000000000000000000');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Revision cannot cross release type';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Revision cannot cross release type [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request SET current_revision_id='0000000b-0000-4000-8000-000000000001',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000004'; SET CONSTRAINTS ALL IMMEDIATE;$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Current revision cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Current revision cannot cross request [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.workflow_instance(request_id,revision_id,matched_rule_id,resolved_route,lifecycle,planned_executor_id,acceptor_id) VALUES('0000000a-0000-4000-8000-000000000004','0000000b-0000-4000-8000-000000000003','X','["X"]'::jsonb,'C','00000002-0000-4000-8000-000000000007','00000002-0000-4000-8000-000000000002');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Workflow revision cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Workflow revision cannot cross request [23505]' AS database_test;

INSERT INTO eas.request_revision(id,request_id,revision_no,release_id,department_id,payload,submitted_by,payload_sha256) VALUES('0000000b-0000-4000-8000-000000000004','0000000a-0000-4000-8000-000000000004',1,'00000003-0000-4000-8000-000000000001','00000001-0000-4000-8000-000000000002','{"title":"Demo leave request","reason":"Personal leave for demonstration","start_date":"2026-12-01","end_date":"2026-12-02","handover_user_id":"00000002-0000-4000-8000-000000000002"}'::jsonb,'00000002-0000-4000-8000-000000000002','0000000000000000000000000000000000000000000000000000000000000000');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.workflow_instance(request_id,revision_id,matched_rule_id,resolved_route,lifecycle) VALUES('0000000a-0000-4000-8000-000000000005','0000000b-0000-4000-8000-000000000004','X','["X"]'::jsonb,'A');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Workflow composite FK isolates request ownership';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Workflow composite FK isolates request ownership [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.workflow_instance(request_id,revision_id,matched_rule_id,resolved_route,lifecycle) VALUES('0000000a-0000-4000-8000-000000000001','0000000b-0000-4000-8000-000000000004','X','["X"]'::jsonb,'A');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Only one ACTIVE instance per request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Only one ACTIVE instance per request [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_step(request_id,instance_id,step_no,assignee_id) VALUES('0000000a-0000-4000-8000-000000000004','0000000c-0000-4000-8000-000000000001',2,'00000002-0000-4000-8000-000000000004');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Approval step cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Approval step cannot cross request [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_step(request_id,instance_id,step_no,assignee_id,state,activated_at) VALUES('0000000a-0000-4000-8000-000000000001','0000000c-0000-4000-8000-000000000001',2,'00000002-0000-4000-8000-000000000004','ACTIVE','2026-01-01T00:00:00.000000Z');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Only one ACTIVE step per instance';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Only one ACTIVE step per instance [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_step(request_id,instance_id,step_no,assignee_id) VALUES('0000000a-0000-4000-8000-000000000001','0000000c-0000-4000-8000-000000000001',2,'00000002-0000-4000-8000-000000000001');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Requester cannot approve own request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Requester cannot approve own request [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_step(request_id,instance_id,step_no,assignee_id) VALUES('0000000a-0000-4000-8000-000000000001','0000000c-0000-4000-8000-000000000001',2,'00000002-0000-4000-8000-000000000003');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Same approver cannot occupy two steps';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Same approver cannot occupy two steps [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000001','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000004','APPROVE');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Wrong actor cannot decide current step';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Wrong actor cannot decide current step [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000004','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','APPROVE');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Approval decision cross-request FK';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Approval decision cross-request FK [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome,reason) VALUES('0000000a-0000-4000-8000-000000000001','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','REJECT','short');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Reject requires reason length';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Reject requires reason length [23514]' AS database_test;

INSERT INTO eas.sla_stage(id,request_id,kind,approval_step_id,due_at) VALUES('00000010-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','APPROVAL','0000000d-0000-4000-8000-000000000001','2099-01-01T00:00:00Z');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.sla_stage(request_id,kind,approval_step_id,due_at) VALUES('0000000a-0000-4000-8000-000000000001','APPROVAL','0000000d-0000-4000-8000-000000000001','2099-01-01T00:00:00Z');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Only one open SLA stage per request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Only one open SLA stage per request [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.sla_stage(request_id,kind,due_at) VALUES('0000000a-0000-4000-8000-000000000004','APPROVAL','2099-01-01T00:00:00Z');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: SLA subtype requires exactly one correct target';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS SLA subtype requires exactly one correct target [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.sla_stage(request_id,kind,approval_step_id,due_at) VALUES('0000000a-0000-4000-8000-000000000004','APPROVAL','0000000d-0000-4000-8000-000000000001','2099-01-01T00:00:00Z');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: SLA target cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS SLA target cannot cross request [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.sla_stage SET due_at=due_at+interval '1 hour' WHERE id='00000010-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: SLA deadline cannot be extended';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS SLA deadline cannot be extended [23514]' AS database_test;

INSERT INTO eas.sla_alert(request_id,stage_id,kind) VALUES('0000000a-0000-4000-8000-000000000001','00000010-0000-4000-8000-000000000001','REMINDER');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.sla_alert(request_id,stage_id,kind) VALUES('0000000a-0000-4000-8000-000000000001','00000010-0000-4000-8000-000000000001','REMINDER');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: SLA alert deduplication';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS SLA alert deduplication [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.sla_alert(request_id,stage_id,kind) VALUES('0000000a-0000-4000-8000-000000000004','00000010-0000-4000-8000-000000000001','BREACH');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: SLA alert cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS SLA alert cannot cross request [23503]' AS database_test;

UPDATE eas.sla_stage SET closed_at=clock_timestamp() WHERE id='00000010-0000-4000-8000-000000000001';

INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000001','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','APPROVE');

UPDATE eas.approval_step SET state='APPROVED',closed_at=clock_timestamp() WHERE id='0000000d-0000-4000-8000-000000000001';

UPDATE eas.request SET status='COMPLETED',approved_at=clock_timestamp(),completed_at=clock_timestamp(),lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000001';

UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=clock_timestamp() WHERE id='0000000c-0000-4000-8000-000000000001';

INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000002','0000000d-0000-4000-8000-000000000002','00000002-0000-4000-8000-000000000003','APPROVE');

UPDATE eas.approval_step SET state='APPROVED',closed_at=clock_timestamp() WHERE id='0000000d-0000-4000-8000-000000000002';

UPDATE eas.request SET status='READY_FOR_EXECUTION',approved_at=clock_timestamp(),completed_at=NULL,lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000002';

INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000003','0000000d-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000003','APPROVE');

UPDATE eas.approval_step SET state='APPROVED',closed_at=clock_timestamp() WHERE id='0000000d-0000-4000-8000-000000000003';

UPDATE eas.request SET status='READY_FOR_EXECUTION',approved_at=clock_timestamp(),completed_at=NULL,lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

DO $test$ BEGIN IF NOT coalesce(((SELECT status='COMPLETED' AND approved_at IS NOT NULL AND completed_at IS NOT NULL FROM eas.request WHERE id='0000000a-0000-4000-8000-000000000001')),false) THEN RAISE EXCEPTION 'FAIL Lifecycle A completes after approval'; END IF; END $test$;
SELECT 'PASS Lifecycle A completes after approval' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000001','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','APPROVE');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Second approval decision rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Second approval decision rejected [23514]' AS database_test;

SET LOCAL ROLE eas_migration;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request_revision SET payload='{}' WHERE id='0000000b-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Revision immutable even for schema owner';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Revision immutable even for schema owner [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.approval_decision SET outcome='REJECT' WHERE step_id='0000000d-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Decision immutable even for schema owner';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Decision immutable even for schema owner [23514]' AS database_test;

SET LOCAL ROLE eas_api;

INSERT INTO eas.execution_attempt(id,request_id,instance_id,attempt_no,executor_id) VALUES('0000000e-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002','0000000c-0000-4000-8000-000000000002',1,'00000002-0000-4000-8000-000000000006');

UPDATE eas.execution_attempt SET state='RUNNING',started_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000002'; UPDATE eas.request SET status='IN_PROGRESS',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000002';

INSERT INTO eas.execution_attempt(id,request_id,instance_id,attempt_no,executor_id) VALUES('0000000e-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003','0000000c-0000-4000-8000-000000000003',1,'00000002-0000-4000-8000-000000000007');

UPDATE eas.execution_attempt SET state='RUNNING',started_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000003'; UPDATE eas.request SET status='IN_PROGRESS',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.execution_attempt(request_id,instance_id,attempt_no,executor_id) VALUES('0000000a-0000-4000-8000-000000000003','0000000c-0000-4000-8000-000000000003',2,'00000002-0000-4000-8000-000000000007');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: One current execution attempt per instance';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS One current execution attempt per instance [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.execution_attempt(request_id,instance_id,attempt_no,executor_id) VALUES('0000000a-0000-4000-8000-000000000001','0000000c-0000-4000-8000-000000000001',1,'00000002-0000-4000-8000-000000000006');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Execution cannot exist on A';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Execution cannot exist on A [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.execution_attempt SET executor_id='00000002-0000-4000-8000-000000000002' WHERE id='0000000e-0000-4000-8000-000000000003'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: RUNNING executor cannot be overwritten';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS RUNNING executor cannot be overwritten [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.execution_issue(request_id,attempt_id,actor_id,kind,reason) VALUES('0000000a-0000-4000-8000-000000000004','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000007','BLOCKED','Fixture blocking reason');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Execution issue cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Execution issue cannot cross request [23503]' AS database_test;

INSERT INTO eas.execution_issue(request_id,attempt_id,actor_id,kind,reason) VALUES('0000000a-0000-4000-8000-000000000003','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000007','BLOCKED','Fixture blocking reason');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='SUCCESS',result_note='Fixture result accepted',external_reference='TEST-B',submitted_at=clock_timestamp(),closed_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000002'; SET CONSTRAINTS ALL IMMEDIATE;$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: B finish without evidence rejected at commit boundary';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS B finish without evidence rejected at commit boundary [23514]' AS database_test;

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002','00000002-0000-4000-8000-000000000006','test-only/no-object/0000000f-0000-4000-8000-000000000002','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.execution_attachment(attempt_id,attachment_id,request_id) VALUES('0000000e-0000-4000-8000-000000000002','0000000f-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000002');

UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='SUCCESS',result_note='Fixture result completed',external_reference='TEST-B',submitted_at=clock_timestamp(),closed_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000002'; UPDATE eas.request SET status='COMPLETED',completed_at=clock_timestamp(),lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000002'; UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=clock_timestamp() WHERE id='0000000c-0000-4000-8000-000000000002';

DO $test$ BEGIN IF NOT coalesce(((SELECT status='COMPLETED' FROM eas.request WHERE id='0000000a-0000-4000-8000-000000000002')),false) THEN RAISE EXCEPTION 'FAIL Lifecycle B completes with evidence'; END IF; END $test$;
SELECT 'PASS Lifecycle B completes with evidence' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.execution_attempt(request_id,instance_id,attempt_no,executor_id) VALUES('0000000a-0000-4000-8000-000000000004','0000000c-0000-4000-8000-000000000002',2,'00000002-0000-4000-8000-000000000006');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Execution attempt composite FK rejects cross-request target';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Execution attempt composite FK rejects cross-request target [23503]' AS database_test;

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','test-only/no-object/0000000f-0000-4000-8000-000000000003','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.execution_attachment(attempt_id,attachment_id,request_id) VALUES('0000000e-0000-4000-8000-000000000003','0000000f-0000-4000-8000-000000000003','0000000a-0000-4000-8000-000000000003');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Evidence must be uploaded by executor';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Evidence must be uploaded by executor [23514]' AS database_test;

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000004','0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000007','test-only/no-object/0000000f-0000-4000-8000-000000000004','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.execution_attachment(attempt_id,attachment_id,request_id) VALUES('0000000e-0000-4000-8000-000000000003','0000000f-0000-4000-8000-000000000004','0000000a-0000-4000-8000-000000000003');

UPDATE eas.execution_attempt SET state='SUBMITTED',result_note='Fixture equipment installed',external_reference='TEST-C',submitted_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000003'; UPDATE eas.request SET status='WAITING_FOR_ACCEPTANCE',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.execution_attempt SET result_note='Overwrite submitted proof' WHERE id='0000000e-0000-4000-8000-000000000003'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Submitted result cannot be changed';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Submitted result cannot be changed [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000003','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000002','ACCEPT');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Wrong acceptor cannot accept';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Wrong acceptor cannot accept [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000004','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','ACCEPT');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Acceptance decision cannot cross request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Acceptance decision cannot cross request [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.workflow_instance SET acceptor_id='00000002-0000-4000-8000-000000000007' WHERE id='0000000c-0000-4000-8000-000000000003'; INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000003','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000007','ACCEPT');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Executor cannot accept own work even after reassignment';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Executor cannot accept own work even after reassignment [23514]' AS database_test;

INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome,reason) VALUES('0000000a-0000-4000-8000-000000000003','0000000e-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000001','REWORK','Fixture requires another attempt');

UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='REWORK',closed_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000003'; UPDATE eas.request SET status='READY_FOR_EXECUTION',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

INSERT INTO eas.execution_attempt(id,request_id,instance_id,attempt_no,executor_id) VALUES('0000000e-0000-4000-8000-000000000004','0000000a-0000-4000-8000-000000000003','0000000c-0000-4000-8000-000000000003',2,'00000002-0000-4000-8000-000000000007');

DO $test$ BEGIN IF NOT coalesce(((SELECT count(*)=2 FROM eas.execution_attempt WHERE instance_id='0000000c-0000-4000-8000-000000000003') AND (SELECT closure_kind='REWORK' FROM eas.execution_attempt WHERE id='0000000e-0000-4000-8000-000000000003')),false) THEN RAISE EXCEPTION 'FAIL REWORK creates new attempt without replacing prior result'; END IF; END $test$;
SELECT 'PASS REWORK creates new attempt without replacing prior result' AS database_test;

UPDATE eas.execution_attempt SET state='RUNNING',started_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000004'; UPDATE eas.request SET status='IN_PROGRESS',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

INSERT INTO eas.sla_stage(id,request_id,kind,attempt_id,due_at) VALUES('00000010-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000003','EXECUTION','0000000e-0000-4000-8000-000000000004','2099-01-01T00:00:00Z');

UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='REASSIGNED',closed_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000004'; UPDATE eas.request SET status='READY_FOR_EXECUTION',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

INSERT INTO eas.execution_attempt(id,request_id,instance_id,attempt_no,executor_id) VALUES('0000000e-0000-4000-8000-000000000005','0000000a-0000-4000-8000-000000000003','0000000c-0000-4000-8000-000000000003',3,'00000002-0000-4000-8000-000000000006');

UPDATE eas.workflow_instance SET planned_executor_id='00000002-0000-4000-8000-000000000006' WHERE id='0000000c-0000-4000-8000-000000000003'; UPDATE eas.sla_stage SET attempt_id='0000000e-0000-4000-8000-000000000005' WHERE id='00000010-0000-4000-8000-000000000002';

DO $test$ BEGIN IF NOT coalesce(((SELECT attempt_id='0000000e-0000-4000-8000-000000000005' AND due_at='2099-01-01T00:00:00Z' FROM eas.sla_stage WHERE id='00000010-0000-4000-8000-000000000002')),false) THEN RAISE EXCEPTION 'FAIL RUNNING reassignment preserves SLA identity and deadline'; END IF; END $test$;
SELECT 'PASS RUNNING reassignment preserves SLA identity and deadline' AS database_test;

UPDATE eas.execution_attempt SET state='RUNNING',started_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000005'; UPDATE eas.request SET status='IN_PROGRESS',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003';

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000005','0000000a-0000-4000-8000-000000000003','00000002-0000-4000-8000-000000000006','test-only/no-object/0000000f-0000-4000-8000-000000000005','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.execution_attachment(attempt_id,attachment_id,request_id) VALUES('0000000e-0000-4000-8000-000000000005','0000000f-0000-4000-8000-000000000005','0000000a-0000-4000-8000-000000000003');

UPDATE eas.execution_attempt SET state='SUBMITTED',result_note='Fixture rework resolved',external_reference='TEST-C-FINAL',submitted_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000005'; UPDATE eas.request SET status='WAITING_FOR_ACCEPTANCE',lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003'; UPDATE eas.sla_stage SET closed_at=clock_timestamp() WHERE id='00000010-0000-4000-8000-000000000002';

INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000003','0000000e-0000-4000-8000-000000000005','00000002-0000-4000-8000-000000000001','ACCEPT');

UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='ACCEPTED',closed_at=clock_timestamp() WHERE id='0000000e-0000-4000-8000-000000000005'; UPDATE eas.request SET status='COMPLETED',completed_at=clock_timestamp(),lock_version=lock_version+1,updated_at=clock_timestamp() WHERE id='0000000a-0000-4000-8000-000000000003'; UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=clock_timestamp() WHERE id='0000000c-0000-4000-8000-000000000003';

DO $test$ BEGIN IF NOT coalesce(((SELECT status='COMPLETED' FROM eas.request WHERE id='0000000a-0000-4000-8000-000000000003') AND (SELECT count(*)=3 FROM eas.execution_attempt WHERE request_id='0000000a-0000-4000-8000-000000000003')),false) THEN RAISE EXCEPTION 'FAIL Lifecycle C completes after acceptance with retained attempts'; END IF; END $test$;
SELECT 'PASS Lifecycle C completes after acceptance with retained attempts' AS database_test;

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000006','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000006','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','QUEUED',0,'2026-01-01T00:00:00.000000Z',NULL);

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000006','00000002-0000-4000-8000-000000000002');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Unscanned file cannot be attached';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Unscanned file cannot be attached [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Cross-request file attachment rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23503' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Cross-request file attachment rejected [23503]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','fixture-backslash','1','bad\file.pdf','application/pdf',10,'0000000000000000000000000000000000000000000000000000000000000000');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Path separator in original filename rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Path separator in original filename rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','fixture-large','1','large.pdf','application/pdf',10485761,'0000000000000000000000000000000000000000000000000000000000000000');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: File larger than 10 MiB rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS File larger than 10 MiB rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','fixture-mime','1','bad.exe','application/octet-stream',10,'0000000000000000000000000000000000000000000000000000000000000000');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Unsupported MIME rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Unsupported MIME rejected [23514]' AS database_test;

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000007','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000007','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000007','00000002-0000-4000-8000-000000000002');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000008','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000008','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000008','00000002-0000-4000-8000-000000000002');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000009','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000009','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000009','00000002-0000-4000-8000-000000000002');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000010','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000010','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000010','00000002-0000-4000-8000-000000000002');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000011','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000011','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000011','00000002-0000-4000-8000-000000000002');

INSERT INTO eas.attachment(id,request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256,scan_state,scan_attempts,created_at,scanned_at) VALUES('0000000f-0000-4000-8000-000000000012','0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','test-only/no-object/0000000f-0000-4000-8000-000000000012','FIXTURE-NO-OBJECT','fixture.pdf','application/pdf',100,'0000000000000000000000000000000000000000000000000000000000000000','CLEAN',1,'2026-01-01T00:00:00.000000Z','2026-01-01T00:00:00.000000Z');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by) VALUES('0000000a-0000-4000-8000-000000000004','0000000f-0000-4000-8000-000000000012','00000002-0000-4000-8000-000000000002');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Sixth selected draft file rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Sixth selected draft file rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.attachment SET deleted_at=clock_timestamp() WHERE id='0000000f-0000-4000-8000-000000000004'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Referenced attachment cannot be tombstoned';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Referenced attachment cannot be tombstoned [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.revision_attachment(request_id,revision_id,attachment_id) VALUES('0000000a-0000-4000-8000-000000000003','0000000b-0000-4000-8000-000000000003','0000000f-0000-4000-8000-000000000003');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Historical revision cannot receive late files';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Historical revision cannot receive late files [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-1','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-2','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-3','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-4','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-5','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-6','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-7','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-8','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-9','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-10','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-11','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-12','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-13','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-14','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-15','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-16','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-17','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-18','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-19','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-20','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');INSERT INTO eas.attachment(request_id,uploader_id,storage_key,object_version,original_name,mime,size_bytes,sha256) VALUES('0000000a-0000-4000-8000-000000000004','00000002-0000-4000-8000-000000000002','quota-21','1','quota.pdf','application/pdf',10485760,'0000000000000000000000000000000000000000000000000000000000000000');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Aggregate quota 200 MiB enforced under request lock';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Aggregate quota 200 MiB enforced under request lock [23514]' AS database_test;

INSERT INTO eas.audit_event(id,request_id,seq,actor_id,actor_kind,action,target_type,target_id,details,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000011-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001',1,'00000002-0000-4000-8000-000000000003','HUMAN','DB_FIXTURE','request','0000000a-0000-4000-8000-000000000001','{"test":true}'::jsonb,'00000012-0000-4000-8000-000000000001','2026-01-01T00:00:00.000000Z',1,'0000000000000000000000000000000000000000000000000000000000000000','1111111111111111111111111111111111111111111111111111111111111111');

DO $test$ BEGIN IF NOT coalesce(((SELECT seq=1 AND last_hash='1111111111111111111111111111111111111111111111111111111111111111' FROM eas.audit_head WHERE scope_key='REQ:0000000a-0000-4000-8000-000000000001')),false) THEN RAISE EXCEPTION 'FAIL Audit append advances request head atomically'; END IF; END $test$;
SELECT 'PASS Audit append advances request head atomically' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.audit_event(id,request_id,seq,actor_id,actor_kind,action,target_type,target_id,details,correlation_id,occurred_at,hash_version,prev_hash,hash) VALUES('00000011-0000-4000-8000-000000000002','0000000a-0000-4000-8000-000000000001',2,'00000002-0000-4000-8000-000000000003','HUMAN','DB_FIXTURE','request','0000000a-0000-4000-8000-000000000001','{"test":true}'::jsonb,'00000012-0000-4000-8000-000000000001','2026-01-01T00:00:00.000000Z',1,'0000000000000000000000000000000000000000000000000000000000000000','1111111111111111111111111111111111111111111111111111111111111111');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Audit previous hash mismatch rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Audit previous hash mismatch rejected [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$DELETE FROM eas.audit_event WHERE id='00000011-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: API cannot delete audit event';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS API cannot delete audit event [42501]' AS database_test;

INSERT INTO eas.outbox_event(id,request_id,event_type,payload,dedupe_key) VALUES('00000013-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','DB_FIXTURE','{"request_id":"0000000a-0000-4000-8000-000000000001"}'::jsonb,'DBTEST-1');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.outbox_event(event_type,payload,dedupe_key) VALUES('DB_FIXTURE','{}'::jsonb,'DBTEST-1');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Outbox dedupe key uniqueness';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Outbox dedupe key uniqueness [23505]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.outbox_event(event_type,payload,dedupe_key,state) VALUES('DB_FIXTURE','{}'::jsonb,'DBTEST-BAD','PROCESSING');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: PROCESSING requires lease token and attempts';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS PROCESSING requires lease token and attempts [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.outbox_event(event_type,payload,dedupe_key,state,attempts) VALUES('DB_FIXTURE','{}'::jsonb,'DBTEST-DEAD','DEAD',1);$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: DEAD requires four attempts';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS DEAD requires four attempts [23514]' AS database_test;

INSERT INTO eas.notification(event_id,recipient_id,request_id,label) VALUES('00000013-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','Fixture ready');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.notification(event_id,recipient_id,request_id,label) VALUES('00000013-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000002',NULL,'Bad scope');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Notification cannot discard event request scope';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Notification cannot discard event request scope [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.notification(event_id,recipient_id,request_id,label) VALUES('00000013-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000001','Duplicate');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Notification duplicate delivery rejected';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Notification duplicate delivery rejected [23505]' AS database_test;

UPDATE eas.notification SET read_at=clock_timestamp() WHERE event_id='00000013-0000-4000-8000-000000000001';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.notification SET read_at=NULL WHERE event_id='00000013-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Notification first read cannot be removed';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Notification first read cannot be removed [23514]' AS database_test;

INSERT INTO eas.idempotency_record(id,actor_id,command_scope,key,request_hash,http_status,response_body,request_id) VALUES('00000014-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000001','POST /requests/demo/submit','00000015-0000-4000-8000-000000000001','0000000000000000000000000000000000000000000000000000000000000000',200,'{"id":"0000000a-0000-4000-8000-000000000001"}'::jsonb,'0000000a-0000-4000-8000-000000000001');

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.idempotency_record(actor_id,command_scope,key,request_hash,http_status,response_body,request_id) VALUES('00000002-0000-4000-8000-000000000001','POST /requests/demo/submit','00000015-0000-4000-8000-000000000001','0000000000000000000000000000000000000000000000000000000000000000',200,'{"id":"0000000a-0000-4000-8000-000000000001"}'::jsonb,'0000000a-0000-4000-8000-000000000001');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Idempotency scope uniqueness';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23505' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Idempotency scope uniqueness [23505]' AS database_test;

SET LOCAL ROLE eas_worker;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome) VALUES('0000000a-0000-4000-8000-000000000001','0000000d-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000003','APPROVE');$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Worker cannot approve a request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Worker cannot approve a request [42501]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.idempotency_record SET response_body=NULL WHERE id='00000014-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Idempotency response cannot clear before 7 days';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Idempotency response cannot clear before 7 days [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$DELETE FROM eas.idempotency_record WHERE id='00000014-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Idempotency tombstone cannot delete before 30 days';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Idempotency tombstone cannot delete before 30 days [23514]' AS database_test;

UPDATE eas.outbox_event SET state='PROCESSING',attempts=attempts+1,lease_token='00000016-0000-4000-8000-000000000001',lease_until=clock_timestamp()+interval '60 seconds' WHERE id='00000013-0000-4000-8000-000000000001';

UPDATE eas.outbox_event SET state='SENT',sent_at=clock_timestamp(),lease_token=NULL,lease_until=NULL WHERE id='00000013-0000-4000-8000-000000000001';

UPDATE eas.attachment SET scan_state='CLEAN',scan_attempts=1,scanned_at=clock_timestamp() WHERE id='0000000f-0000-4000-8000-000000000006';

SET LOCAL ROLE anon;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$SELECT * FROM eas.request$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: anon cannot read private EAS data';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS anon cannot read private EAS data [42501]' AS database_test;

SET LOCAL ROLE authenticated;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$SELECT * FROM eas.request$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: authenticated cannot read private EAS data';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS authenticated cannot read private EAS data [42501]' AS database_test;

SET LOCAL ROLE service_role;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$SELECT * FROM eas.request$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: service_role cannot read private EAS data';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS service_role cannot read private EAS data [42501]' AS database_test;

SET LOCAL ROLE eas_backup;

DO $test$ BEGIN IF NOT coalesce(((SELECT count(*)=5 FROM eas.request)),false) THEN RAISE EXCEPTION 'FAIL Backup role can read all request rows'; END IF; END $test$;
SELECT 'PASS Backup role can read all request rows' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.request SET lock_version=lock_version+1 WHERE id='0000000a-0000-4000-8000-000000000004'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Backup role cannot mutate';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Backup role cannot mutate [42501]' AS database_test;

SET LOCAL ROLE eas_api;

INSERT INTO eas.privacy_case(id,subject_user_id,case_type,status,due_at,policy_version,owner_id,decision_reference) VALUES('00000017-0000-4000-8000-000000000001','00000002-0000-4000-8000-000000000002','ERASE','APPROVED','2099-01-01T00:00:00Z','DBTEST-ONLY','00000002-0000-4000-8000-000000000008','TEST-APPROVAL');

INSERT INTO eas.retention_hold(id,request_id,reason,authority_reference,set_by) VALUES('00000018-0000-4000-8000-000000000001','0000000a-0000-4000-8000-000000000004','Hold for database regression fixture','TEST-HOLD','00000002-0000-4000-8000-000000000008');

SET LOCAL ROLE eas_privacy;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$DELETE FROM eas.draft_attachment WHERE request_id='0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.attachment WHERE id='0000000f-0000-4000-8000-000000000012'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Privacy deletion needs case context';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Privacy deletion needs case context [42501]' AS database_test;

SET LOCAL eas.privacy_case_id='00000017-0000-4000-8000-000000000001';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$DELETE FROM eas.attachment WHERE id='0000000f-0000-4000-8000-000000000012'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Open legal hold blocks authorized privacy deletion';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Open legal hold blocks authorized privacy deletion [23514]' AS database_test;

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$DELETE FROM eas.request WHERE id='0000000a-0000-4000-8000-000000000005'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Case for different subject cannot delete request';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'42501' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Case for different subject cannot delete request [42501]' AS database_test;

SET LOCAL ROLE eas_api;

UPDATE eas.retention_hold SET released_at=clock_timestamp(),released_by='00000002-0000-4000-8000-000000000008' WHERE id='00000018-0000-4000-8000-000000000001';

DO $test$ BEGIN
 BEGIN
 EXECUTE $operation$UPDATE eas.retention_hold SET released_at=NULL,released_by=NULL WHERE id='00000018-0000-4000-8000-000000000001'$operation$;
 RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='Expected rejection: Released hold cannot be reopened by update';
 EXCEPTION WHEN OTHERS THEN
 IF SQLSTATE<>'23514' THEN RAISE; END IF;
 END;
END $test$;
SELECT 'PASS Released hold cannot be reopened by update [23514]' AS database_test;

SET LOCAL ROLE eas_privacy;

DELETE FROM eas.draft_attachment WHERE request_id='0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.attachment WHERE request_id='0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.request_revision WHERE request_id='0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.retention_hold WHERE request_id='0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.audit_head WHERE scope_key='REQ:0000000a-0000-4000-8000-000000000004'; DELETE FROM eas.request WHERE id='0000000a-0000-4000-8000-000000000004';

RESET ROLE;

SET CONSTRAINTS ALL IMMEDIATE;

DO $test$ BEGIN IF NOT coalesce(((SELECT count(*)=3 FROM eas.request WHERE status='COMPLETED')),false) THEN RAISE EXCEPTION 'FAIL Three core lifecycles preserve complete final state'; END IF; END $test$;
SELECT 'PASS Three core lifecycles preserve complete final state' AS database_test;

ROLLBACK;
