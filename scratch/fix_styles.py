with open(r'web_client/src/eas-enhancements.css', 'a', encoding='utf-8') as f:
    f.write('''

/* Modal Backdrop & Card for User Management & Phase 4 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(4px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeIn 0.2s ease-out;
}
.modal-card {
  background: var(--bg-card, #ffffff);
  color: var(--text-main, #0f172a);
  border-radius: 14px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.35);
  width: 100%;
  max-width: 540px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
  border: 1px solid var(--border-color, #e2e8f0);
  animation: zoomIn 0.2s ease-out;
}
@keyframes zoomIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* Dark Mode Overrides for Phase 4 */
[data-theme="dark"], body.dark, .dark {
  --bg-card: #132238;
  --border-color: #1e3a5f;
  --text-main: #f8fafc;
}

[data-theme="dark"] .user-management-table th,
[data-theme="dark"] .rbac-matrix-table th,
[data-theme="dark"] .stage-detail-table th {
  background: #0f1b2d !important;
  color: #94a3b8 !important;
  border-bottom: 1px solid #1e3a5f !important;
}

[data-theme="dark"] .user-management-table td,
[data-theme="dark"] .rbac-matrix-table td,
[data-theme="dark"] .stage-detail-table td {
  border-bottom: 1px solid #162a45 !important;
  color: #e2e8f0;
}

[data-theme="dark"] .user-full-name strong,
[data-theme="dark"] .module-display-name,
[data-theme="dark"] .drawer-header h2,
[data-theme="dark"] .modal-head h2 {
  color: #f8fafc !important;
}

[data-theme="dark"] .drawer-panel,
[data-theme="dark"] .modal-card {
  background: #101c2e !important;
  color: #f8fafc !important;
  border: 1px solid #1e3a5f !important;
}

[data-theme="dark"] .table-filter-bar,
[data-theme="dark"] .user-override-header-bar {
  background: #101c2e !important;
  border: 1px solid #1e3a5f !important;
}

[data-theme="dark"] .search-input-wrap,
[data-theme="dark"] .filter-select,
[data-theme="dark"] .input-select,
[data-theme="dark"] .input-text {
  background: #0b1523 !important;
  border-color: #1e3a5f !important;
  color: #f8fafc !important;
}

[data-theme="dark"] .dept-tag,
[data-theme="dark"] .drilldown-badge-btn,
[data-theme="dark"] .role-pill-btn {
  background: #14243b !important;
  border-color: #1e3a5f !important;
  color: #cbd5e1 !important;
}

[data-theme="dark"] .drilldown-badge-btn:hover,
[data-theme="dark"] .role-pill-btn:hover {
  background: #1a3252 !important;
  color: #60a5fa !important;
}

[data-theme="dark"] .role-pill-btn.active {
  background: #2563eb !important;
  border-color: #2563eb !important;
  color: #ffffff !important;
}

[data-theme="dark"] .user-override-summary-badge {
  background: #14243b !important;
  color: #cbd5e1 !important;
}

[data-theme="dark"] .empty-user-select-box {
  background: #0b1523 !important;
  border-color: #1e3a5f !important;
}

[data-theme="dark"] .stage-tag {
  background: #1e3a5f !important;
  color: #93c5fd !important;
}
''')
print("Fixed styles successfully!")

