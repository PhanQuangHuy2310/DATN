import joblib, json, os
import numpy as np

models_dir = 'D:/GitHub/DATN/ai_service/models'
configs = {
    'finance': ('risk_model_finance.pkl', 'feature_cols_finance.json'),
    'hr':      ('risk_model_hr.pkl',      'feature_cols_hr.json'),
    'it':      ('risk_model_it.pkl',      'feature_cols_it.json'),
    'master':  ('risk_model.pkl',         'feature_columns.json'),
}
for domain, (mf, ff) in configs.items():
    mp = os.path.join(models_dir, mf)
    fp = os.path.join(models_dir, ff)
    if not os.path.exists(mp):
        print(f"[{domain}] MISSING: {mp}")
        continue
    m = joblib.load(mp)
    size_mb = os.path.getsize(mp) / 1024 / 1024
    with open(fp, encoding='utf-8') as f:
        meta = json.load(f)
    feat_cols = meta['feature_cols'] if isinstance(meta, dict) else meta
    p = m.get_params()
    print(f"=== {domain.upper()} MODEL ===")
    print(f"  File size        : {size_mb:.1f} MB")
    print(f"  n_estimators     : {p['n_estimators']}")
    print(f"  max_depth        : {p['max_depth']}")
    print(f"  learning_rate    : {p['learning_rate']}")
    print(f"  subsample        : {p['subsample']}")
    print(f"  colsample_bytree : {p['colsample_bytree']}")
    print(f"  tree_method      : {p['tree_method']}")
    print(f"  best_iteration   : {m.best_iteration}")
    print(f"  num_features     : {len(feat_cols)}")
    print(f"  features         : {feat_cols}")
    imp = m.feature_importances_
    top5 = sorted(zip(feat_cols, imp), key=lambda x: -x[1])[:5]
    print("  Top 5 Feature Importance:")
    for name, val in top5:
        bar = "#" * int(val * 200)
        print(f"    {name:<30} {val*100:5.2f}%  {bar}")
    print()
