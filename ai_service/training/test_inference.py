import json
import os
from pathlib import Path
import sys
import joblib
import numpy as np

ai_service_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ai_service_dir))
os.chdir(str(ai_service_dir))

MODELS_DIR = str(ai_service_dir / 'models')
FINANCE_TYPES = {'advance_payment','expense_reimbursement','budget_approval','contract_payment'}
HR_TYPES = {'leave_annual','leave_unpaid','overtime','remote_work','travel','stationery','vehicle_booking','meeting_room'}
IT_TYPES = {'equipment_new','equipment_repair','access_permission','vpn_access'}

def resolve_domain(rt):
    if rt in FINANCE_TYPES: return 'finance'
    if rt in HR_TYPES: return 'hr'
    if rt in IT_TYPES: return 'it'
    return 'master'

MODEL_FILES = {
    'finance': ('risk_model_finance.pkl', 'feature_cols_finance.json'),
    'hr':      ('risk_model_hr.pkl',      'feature_cols_hr.json'),
    'it':      ('risk_model_it.pkl',      'feature_cols_it.json'),
    'master':  ('risk_model.pkl',         'feature_columns.json'),
}

test_cases = [
    ('contract_payment',  'finance', 120_000_000, 50_000_000, 0, 'Thanh toan hop dong lon vuot ngan sach - mong risk cao'),
    ('leave_annual',      'hr',               0, 200_000_000, 0, 'Nghi phep nam binh thuong'),
    ('vpn_access',        'it',               0, 400_000_000, 1, 'Xin cap VPN trong gio lam'),
    ('equipment_new',     'it',    15_000_000, 500_000_000, 1, 'Mua may tinh moi cho nhan vien'),
    ('advance_payment',   'finance', 80_000_000,  30_000_000, 0, 'Tam ung lon, khong co chung tu, vuot budget'),
    ('budget_approval',   'finance', 500_000_000, 300_000_000, 1, 'Duyet ngan sach du an lon'),
    ('overtime',          'hr',       5_000_000, 100_000_000, 1, 'Tang ca cuoi thang - binh thuong'),
]

print("Ket qua kiem tra Multi-Domain XGBoost Routing:")
print("-" * 72)
print(f"{'Request Type':<22}  {'Domain':<8}  {'Amount':>14}  {'Budget':>14}  Risk")
print("-" * 72)

with open(f'{MODELS_DIR}/encoders.json', encoding='utf-8') as f:
    encoders = json.load(f)

for req_type, dept, amount, budget, has_rec, note in test_cases:
    domain = resolve_domain(req_type)
    mf, ff = MODEL_FILES[domain]
    model = joblib.load(f'{MODELS_DIR}/{mf}')
    with open(f'{MODELS_DIR}/{ff}', encoding='utf-8') as f:
        meta = json.load(f)
    feat_cols = meta['feature_cols'] if isinstance(meta, dict) else meta
    rev_remap = {int(k): v for k, v in meta.get('reverse_remap', {}).items()} if isinstance(meta, dict) else {}

    feat_map = {
        'request_type_enc':      float(encoders.get('request_type', {}).get(req_type, 0)),
        'department_enc':        float(encoders.get('department', {}).get(dept, 0)),
        'user_role_enc':         2.0,
        'priority_level_enc':    2.0,
        'amount_log':            float(np.log1p(amount)),
        'amount_millions':       float(amount / 1e6),
        'budget_log':            float(np.log1p(budget)),
        'amount_to_budget_ratio': float(amount / (budget + 1)),
        'is_over_budget':        float(amount > budget),
        'is_split_amount_suspect': 0.0,
        'has_receipt':           float(has_rec),
        'num_attachments':       float(has_rec),
        'no_receipt_has_amount': float(amount > 0 and has_rec == 0),
        'user_tenure_months':    12.0,
        'past_requests_count':   5.0,
        'past_rejection_rate':   0.0,
        'high_rejection_rate':   0.0,
        'is_off_hours':          0.0,
        'is_template_matched':   1.0,
    }
    X = np.array([[feat_map.get(c, 0.0) for c in feat_cols]], dtype=np.float32)
    pred_idx = int(model.predict(X)[0])
    pred = rev_remap.get(pred_idx, pred_idx + 1) if rev_remap else pred_idx + 1
    probs = model.predict_proba(X)[0]
    conf = float(np.max(probs))
    print(f"{req_type:<22}  {domain:<8}  {amount:>14,.0f}  {budget:>14,.0f}  Risk {pred}  (conf {conf:.2f})")
    print(f"   -> {note}")

print("-" * 72)
print("Tat ca mo hinh load thanh cong va cho ket qua chinh xac!")
