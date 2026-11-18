-- 24: Vòng phản hồi để AI "sai tối đa 1 lần".
--
--   1. eas.ai_feedback: mỗi lần con người sửa quyết định của AI (thu hồi tự duyệt, đánh dấu chuyển luồng
--      nhầm, chọn ứng viên khác ứng viên AI xếp đầu, bỏ qua đề xuất xử lý) kèm tín hiệu lúc đó. Bảng là bộ
--      nhớ ca (dùng ngay ở quyết định kế tiếp, không cần huấn luyện lại) và là dữ liệu cho học dồn định kỳ.
--      Chỉ thêm; được phép đánh dấu retired_at (admin ngưng dùng một ca) và used_in_training.
--   2. eas.regulation_clause_review: câu quy định có tín hiệu kiểm soát nhưng trình biên dịch không hiểu
--      (điều kiện ngoài schema) được đưa lên hàng chờ của admin kèm cách hiểu do Gemini đề xuất; luật admin
--      duyệt được ghép vào bộ luật ở lần học kế tiếp.
--
-- Chạy được nhiều lần. Rollback: database/migrations/rollback/24_ai_feedback_learning_rollback.sql

BEGIN;
SELECT eas.lock_security(true);

CREATE TABLE IF NOT EXISTS eas.ai_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind varchar(30) NOT NULL CHECK (kind IN (
    'AUTO_APPROVE_REVOKED', 'ESCALATION_UNNECESSARY', 'RANKING_OVERRIDDEN', 'REMEDIATION_DISMISSED')),
  request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE CASCADE,
  type_code varchar(30) NOT NULL,
  subject_id uuid REFERENCES eas.app_user(id) ON DELETE SET NULL,
  actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  case_codes text[] NOT NULL DEFAULT '{}',
  ai_decision jsonb NOT NULL CHECK (jsonb_typeof(ai_decision) = 'object'),
  human_decision jsonb NOT NULL CHECK (jsonb_typeof(human_decision) = 'object'),
  reason varchar(500),
  signals jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(signals) = 'object'),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  retired_at timestamptz,
  retired_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  used_in_training varchar(60)
);
CREATE INDEX IF NOT EXISTS ai_feedback_memory
  ON eas.ai_feedback(kind, type_code, subject_id) WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS ai_feedback_request ON eas.ai_feedback(request_id);
COMMENT ON TABLE eas.ai_feedback IS
  'Con người sửa quyết định của AI: bộ nhớ ca (dùng ngay) và dữ liệu học dồn. Chỉ thêm; chỉ được đánh dấu retired_at/used_in_training.';

CREATE OR REPLACE FUNCTION eas.guard_ai_feedback() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='AI feedback is append-only';
 END IF;
 IF (to_jsonb(NEW) - ARRAY['retired_at','retired_by','used_in_training'])
    IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['retired_at','retired_by','used_in_training'])
    OR (OLD.retired_at IS NOT NULL AND NEW.retired_at IS DISTINCT FROM OLD.retired_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='AI feedback is immutable';
 END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_ai_feedback() OWNER TO eas_migration;
REVOKE EXECUTE ON FUNCTION eas.guard_ai_feedback() FROM PUBLIC;
DROP TRIGGER IF EXISTS ai_feedback_guard ON eas.ai_feedback;
CREATE TRIGGER ai_feedback_guard BEFORE UPDATE OR DELETE ON eas.ai_feedback
  FOR EACH ROW EXECUTE FUNCTION eas.guard_ai_feedback();

CREATE TABLE IF NOT EXISTS eas.regulation_clause_review (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  regulation_code varchar(30) NOT NULL,
  sentence text NOT NULL CHECK (length(btrim(sentence)) BETWEEN 5 AND 2000),
  sentence_sha256 char(64) NOT NULL,
  reason varchar(200) NOT NULL,
  suggestion jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(suggestion) = 'object'),
  state varchar(10) NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING', 'APPROVED', 'REJECTED')),
  approved_rules jsonb CHECK (approved_rules IS NULL OR jsonb_typeof(approved_rules) = 'array'),
  decided_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  decided_at timestamptz,
  note varchar(500),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (regulation_code, sentence_sha256),
  CHECK ((state = 'PENDING') = (decided_at IS NULL)),
  CHECK (state <> 'APPROVED' OR approved_rules IS NOT NULL)
);
COMMENT ON TABLE eas.regulation_clause_review IS
  'Câu quy định AI chưa tự hiểu được: chờ admin duyệt cách hiểu (Gemini đề xuất); luật đã duyệt được ghép vào bộ luật khi AI học lại.';

DO $grants$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['ai_feedback', 'regulation_clause_review'] LOOP
    EXECUTE format('REVOKE ALL ON eas.%I FROM PUBLIC', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON eas.%I TO eas_api, eas_worker', t);
    EXECUTE format('GRANT SELECT ON eas.%I TO eas_backup', t);
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='eas' AND tablename=t AND policyname='backend_read') THEN
      EXECUTE format('CREATE POLICY backend_read ON eas.%I FOR SELECT TO eas_api, eas_worker USING (true)', t);
      EXECUTE format('CREATE POLICY backend_insert ON eas.%I FOR INSERT TO eas_api, eas_worker WITH CHECK (true)', t);
      EXECUTE format('CREATE POLICY backend_update ON eas.%I FOR UPDATE TO eas_api, eas_worker USING (true) WITH CHECK (true)', t);
      EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
    END IF;
  END LOOP;
END
$grants$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;

SELECT to_regclass('eas.ai_feedback') AS feedback, to_regclass('eas.regulation_clause_review') AS clause_review;
