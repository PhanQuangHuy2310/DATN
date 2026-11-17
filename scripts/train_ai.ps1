<#
.SYNOPSIS
  Huấn luyện lại toàn bộ AI của EAS bằng một lệnh: kiểm tra môi trường, sao lưu model cũ,
  (tuỳ chọn) dựng lại dữ liệu công khai, chạy training/train.py, chạy thử và in tóm tắt.

.EXAMPLE
  .\train_ai_local.cmd                      # train đầy đủ (bộ phân loại + 4 mô hình rủi ro)
  .\train_ai_local.cmd -Only nlp            # chỉ bộ phân loại văn bản
  .\train_ai_local.cmd -Only risk           # chỉ bộ chấm điểm rủi ro
  .\train_ai_local.cmd -Only profile        # chỉ mô hình hồ sơ quy trình (mẫu A/B/C, trọng số, tác động quy định)
  .\train_ai_local.cmd -RebuildPublicData   # dựng lại dữ liệu công khai trước khi train
  .\train_ai_local.cmd -CheckOnly           # chỉ nạp model hiện có và đoán thử vài câu
  .\train_ai_local.cmd -Restore 20261117-1030   # khôi phục model từ một bản sao lưu

.NOTES
  Dữ liệu (đều có sẵn trong repo, xem docstring của ai_service/training/train.py):
    api_core/catalog/catalog_v2.json                 58 loại yêu cầu
    ai_service/training/data/request_corpus.json     mẫu câu tổng hợp
    ai_service/training/data/request_public_train.json  câu thật / bán tổng hợp / AI sinh (có nguồn)
    ai_service/training/data/request_eval_*.json     các tập đánh giá, KHÔNG dùng để train
  Model cũ được sao lưu vào ai_service/models/.backup-<thời điểm>/ (đã gitignore).
  -RebuildPublicData cần thư mục workspace/du_lieu_cong_khai (không nằm trong git).
#>
[CmdletBinding()]
param(
    [ValidateSet('nlp', 'risk', 'profile')]
    [string]$Only,
    [switch]$RebuildPublicData,
    [switch]$CheckOnly,
    [int]$Seed = 42,
    [string]$Restore
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root 'ai_service\.venv-ai\Scripts\python.exe'
$Train = Join-Path $Root 'ai_service\training\train.py'
$Models = Join-Path $Root 'ai_service\models'
$Data = Join-Path $Root 'ai_service\training\data'
$PublicDir = Join-Path $Root 'workspace\du_lieu_cong_khai'

function Step([string]$text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail([string]$text) { Write-Host "LỖI: $text" -ForegroundColor Red; exit 1 }

function Invoke-Py {
    param([string[]]$Arguments)
    & $Py @Arguments
    if ($LASTEXITCODE -ne 0) { Fail "lệnh python $($Arguments -join ' ') thoát với mã $LASTEXITCODE" }
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = $Root

# ---------------------------------------------------------------- 0. Khôi phục bản sao lưu
if ($Restore) {
    $src = Join-Path $Models ".backup-$Restore"
    if (-not (Test-Path $src)) {
        $list = (Get-ChildItem $Models -Directory -Force -Filter '.backup-*' | ForEach-Object { $_.Name -replace '^\.backup-', '' }) -join ', '
        Fail "không có bản sao lưu '$Restore'. Hiện có: $list"
    }
    Get-ChildItem $src -File | Where-Object { $_.Name -ne 'train.log' } | Copy-Item -Destination $Models -Force
    Write-Host "Đã khôi phục model từ $src. Khởi động lại AI service để áp dụng." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------- 1. Kiểm tra môi trường
Step '1. Kiểm tra môi trường'
if (-not (Test-Path $Py)) {
    Fail "chưa có ai_service\.venv-ai. Tạo bằng: py -3.11 -m venv ai_service\.venv-ai; ai_service\.venv-ai\Scripts\pip install -r ai_service\requirements-local.txt"
}
# PowerShell 5.1 nuốt dấu " trong tham số gửi cho chương trình ngoài: chỉ dùng nháy đơn trong -c.
Invoke-Py @('-c', "import sklearn, xgboost, pandas, joblib; print('  scikit-learn', sklearn.__version__, '| xgboost', xgboost.__version__)")
$required = @(
    (Join-Path $Root 'api_core\catalog\catalog_v2.json'),
    (Join-Path $Data 'request_corpus.json'),
    (Join-Path $Data 'request_eval_realistic.json'),
    (Join-Path $Data 'request_eval_short.json')
)
foreach ($f in $required) { if (-not (Test-Path $f)) { Fail "thiếu tệp dữ liệu $f" } }
foreach ($f in @('request_public_train.json', 'request_eval_public.json')) {
    if (-not (Test-Path (Join-Path $Data $f))) {
        Write-Host "  CẢNH BÁO: thiếu $f -> bộ phân loại chỉ học dữ liệu tổng hợp" -ForegroundColor Yellow
    }
}
$running = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'training[\\/]train\.py' }
if ($running) { Fail "đang có tiến trình train.py khác chạy (PID $($running.ProcessId -join ', ')). Chờ nó xong hoặc dừng nó trước." }

if ($CheckOnly) {
    Step 'Chạy thử model hiện có'
    Invoke-Py @($Train, '--check')
    exit 0
}

# ---------------------------------------------------------------- 2. Sao lưu model cũ
Step '2. Sao lưu model hiện tại'
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$backup = Join-Path $Models ".backup-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null
Get-ChildItem $Models -File | Copy-Item -Destination $backup
Write-Host "  -> $backup  (khôi phục: .\train_ai_local.cmd -Restore $stamp)"

# ---------------------------------------------------------------- 3. (Tuỳ chọn) Dựng lại dữ liệu công khai
if ($RebuildPublicData) {
    Step '3. Dựng lại dữ liệu công khai'
    if (-not (Test-Path (Join-Path $PublicDir 'scripts'))) { Fail "không có $PublicDir\scripts (thư mục này không nằm trong git)" }
    # Thứ tự: làm sạch phiếu IT -> ghép bộ đánh giá -> đọc giao dịch thẻ -> sinh câu bán tổng hợp -> ghép dữ liệu train
    foreach ($s in @('01_clean_it_tickets.py', '02_build_eval.py', '05_parse_uk_purchase_card.py', '06_uk_card_to_eas.py')) {
        Write-Host "  - $s"
        Invoke-Py @('-I', (Join-Path $PublicDir "scripts\$s"), $PublicDir) | Out-Null
    }
    Write-Host '  - 04_build_train.py'
    Invoke-Py @('-I', (Join-Path $PublicDir 'scripts\04_build_train.py'), $PublicDir, $Data) | Out-Null
    Write-Host '  -> đã ghi request_public_train.json và request_eval_public.json'
} else {
    Step '3. Dùng dữ liệu công khai có sẵn (thêm -RebuildPublicData để dựng lại)'
}

# ---------------------------------------------------------------- 4. Huấn luyện
Step '4. Huấn luyện (mất khoảng 10-20 phút cho lần train đầy đủ)'
$log = Join-Path $backup 'train.log'
$trainArgs = @('-u', $Train, '--seed', $Seed)
if ($Only -and $Only -ne 'profile') { $trainArgs += @('--only', $Only) }
$started = Get-Date
if ($Only -ne 'profile') {
    & $Py @trainArgs 2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) {
        Fail "train.py thất bại (mã $LASTEXITCODE). Model cũ vẫn giữ nguyên; log: $log"
    }
}
if (-not $Only -or $Only -eq 'profile') {
    # Mô hình hồ sơ quy trình: tự kiểm tra SHA-256 của đáp án kịch bản trước khi chạy (báo lỗi nếu đáp án bị sửa).
    Write-Host '  - train_process_profile.py (leave-one-out + 30 kịch bản quy định, khoảng 1-3 phút)'
    $profileTrain = Join-Path $Root 'ai_service\training\train_process_profile.py'
    & $Py -u $profileTrain 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Fail "train_process_profile.py thất bại (mã $LASTEXITCODE); log: $log" }
    Write-Host '  -> báo cáo: ai_service\training\data\process_profile_report.md'
}
$minutes = [Math]::Round(((Get-Date) - $started).TotalMinutes, 1)

# ---------------------------------------------------------------- 5. Chạy thử + tóm tắt
Step '5. Chạy thử model mới'
if ($Only -ne 'profile') { Invoke-Py @($Train, '--check') }

Step "6. Tóm tắt ($minutes phút)"
$summary = @'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
n, r = m.get("nlp_metrics") or {}, m.get("risk_metrics") or {}
pct = lambda x: f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "-"
print(f"  Phiên bản            : {m['pipeline_version']} ({m['trained_at']})")
if n:
    rt, st = n["realistic"]["test"], n["short_inputs"]["test"]
    print(f"  Câu viết tay (test)  : {pct(rt['accuracy'])}  top-3 {pct(rt['top3_accuracy'])}")
    print(f"  Câu rất ngắn (test)  : {pct(st['accuracy'])}")
    pub = n.get("public_test") or {}
    if "ALL_IN_SCOPE" in pub:
        print(f"  Câu thật công khai   : {pct(pub['ALL_IN_SCOPE']['accuracy'])}"
              f"  (phiếu IT {pct(pub.get('it_tickets:manual', {}).get('accuracy'))})")
    if "OUT_OF_SCOPE" in pub:
        print(f"  Ngoài phạm vi gắn cờ : {pct(pub['OUT_OF_SCOPE']['flagged_rate'])}")
    print(f"  Tham số chọn         : C={n['chosen_c']}, trọng số câu bổ sung={n.get('chosen_public_weight', 0)}")
if r:
    print(f"  Rủi ro (master)      : accuracy {pct(r['master']['accuracy'])}, macro-F1 {r['master']['f1_macro']:.3f}")
'@
$summaryPy = Join-Path $backup 'summary.py'
[IO.File]::WriteAllText($summaryPy, $summary, (New-Object Text.UTF8Encoding($false)))
Invoke-Py @($summaryPy, (Join-Path $Models 'model_metadata.json'))

Write-Host "`nBáo cáo chi tiết : ai_service\training\data\training_report.md"
Write-Host "Log lần train    : $log"
Write-Host 'Áp dụng model mới:'
Write-Host '  - Docker  : docker compose restart ai-service   (thư mục models được mount, không cần build lại)'
Write-Host '  - Chạy tay: tắt rồi chạy lại start_ai_local.cmd'
