# Danh mục và cách xuất sơ đồ EAS

## Coverage

| File | Nhóm | Số sơ đồ |
|---|---|---:|
| `01_use_case.md` | Use case/context/workspace | 9 |
| `02_activity.md` | Activity/business/ops/privacy | 10 |
| `03_sequence.md` | Sequence/application/concurrency/DR | 22 |
| `04_state_machine.md` | State machine | 8 |
| `05_architecture_and_data.md` | Architecture, DFD, security, deployment, ERD, sitemap | 19 |
| **Tổng** | | **68** |

Mỗi sơ đồ có ID duy nhất. Không đổi ID sau khi đã tham chiếu trong luận văn hoặc RTM; đổi tên hiển thị không được làm mất trace.

## Xuất hình vector để chèn vào Word/LaTeX

Yêu cầu: Node.js 18+ và Mermaid CLI. Từ thư mục gốc repository:

```powershell
$output = Join-Path $PWD 'docs\rendered'
New-Item -ItemType Directory -Path $output -Force | Out-Null
Get-ChildItem 'docs\diagrams' -Filter '*.md' |
  Where-Object Name -ne 'README.md' |
  ForEach-Object {
    npx --yes '@mermaid-js/mermaid-cli' `
      -i $_.FullName `
      -o (Join-Path $output ($_.BaseName + '.rendered.md')) `
      -b transparent
    if ($LASTEXITCODE -ne 0) { throw "Render failed: $($_.Name)" }
  }
```

Mermaid CLI sẽ tạo Markdown đã thay block bằng liên kết hình và các SVG liên quan. SVG là định dạng ưu tiên để chữ không vỡ khi in A4. Không chỉnh trực tiếp SVG; sửa Mermaid source rồi render lại.

## Quy chuẩn đưa vào luận văn

1. Đặt đoạn giải thích 2–3 đoạn trước hình: mục tiêu, luồng chính và ngoại lệ.
2. Chèn SVG ở chiều rộng đủ đọc, giữ tỷ lệ; hình dày chuyển sang trang landscape hoặc phụ lục.
3. Caption dạng `Hình 2.x: <ID> — <Tên> (Nguồn: Nhóm tác giả)`.
4. Dùng cross-reference tự động của Word/LaTeX.
5. Sau caption ghi trace UC/FR/BR/API/TC ngắn gọn.
6. Không chụp màn hình Mermaid editor để đưa vào báo cáo.

## Quality gate trước khi xuất bản

- Mermaid render không lỗi.
- ID không trùng và mọi link nội bộ tồn tại.
- Trạng thái/actor/endpoint khớp baseline v2.
- Chữ đọc được ở bản in thử 100% và bản PDF 125%.
- Không có tính năng ngoài P0 bị mô tả như hiện trạng.
- Hình kiến trúc có nhãn `Target design` cho đến khi có source/IaC/evidence.
- Test screenshot chỉ dùng actual result, không dùng expected result làm bằng chứng PASS.
