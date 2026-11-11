with open(r'web_client/src/eas-enhancements.css', 'a', encoding='utf-8') as f:
    f.write('''

/* ==========================================================================
   PHASE 4: USER MANAGEMENT, ORG CHART & RBAC MATRIX STYLES
   ========================================================================== */

/* KPI Grid 4 columns */
.kpi-grid-4 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.kpi-value.text-green { color: #16a34a; }
.kpi-value.text-amber { color: #d97706; }
.kpi-value.text-cyan { color: #0284c7; }
.kpi-value.text-blue { color: #2563eb; }

/* Filter Bar */
.table-filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  background: var(--bg-card, #ffffff);
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e2e8f0);
}
.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 260px;
  background: var(--bg-input, #f8fafc);
  border: 1px solid var(--border-color, #cbd5e1);
  padding: 8px 12px;
  border-radius: 8px;
}
.search-input-wrap input {
  border: none;
  background: transparent;
  width: 100%;
  font-size: 13.5px;
  color: var(--text-main, #1e293b);
  outline: none;
}
.filter-select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #cbd5e1);
  background: var(--bg-card, #ffffff);
  font-size: 13.5px;
  color: var(--text-main, #1e293b);
  cursor: pointer;
}
.text-btn {
  font-size: 13px;
  padding: 6px 12px;
  color: #64748b;
  cursor: pointer;
}

/* User Profile Cell */
.user-profile-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-avatar-circle {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  color: #334155;
  border: 2px solid transparent;
}
.user-avatar-circle.border-green { border-color: #22c55e; background: #f0fdf4; color: #166534; }
.user-avatar-circle.border-amber { border-color: #f59e0b; background: #fffbeb; color: #92400e; }
.user-avatar-circle.border-blue { border-color: #3b82f6; background: #eff6ff; color: #1e40af; }
.user-avatar-circle.border-gray { border-color: #cbd5e1; background: #f8fafc; color: #64748b; }

.user-full-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-main, #0f172a);
}
.user-meta-sub {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.dept-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12.5px;
  font-weight: 500;
}
.job-title-sub {
  font-size: 12px;
  color: #64748b;
  margin-top: 3px;
}

/* Status Badges */
.status-badge-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  width: fit-content;
}
.status-working {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #bbf7d0;
}
.status-leave {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}
.status-trip {
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
}
.status-locked {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
.status-detail-hint {
  font-size: 11px;
  color: #64748b;
  max-width: 220px;
  line-height: 1.3;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.dot-green { background: #22c55e; }
.dot-amber { background: #f59e0b; }
.dot-blue { background: #0284c7; }
.dot-red { background: #ef4444; }

/* Drilldown Badge Button */
.drilldown-badge-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #1e293b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.drilldown-badge-btn:hover {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
  transform: translateY(-1px);
}
.drilldown-count {
  font-weight: 700;
  color: #2563eb;
}
.drilldown-label {
  font-size: 12px;
  color: #64748b;
}

/* Action Buttons */
.action-buttons-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.btn-icon-subtle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-icon-subtle:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #0f172a;
}
.btn-icon-subtle.text-red:hover {
  background: #fee2e2;
  color: #dc2626;
  border-color: #fca5a5;
}
.btn-icon-subtle.text-green:hover {
  background: #dcfce7;
  color: #16a34a;
  border-color: #86efac;
}

/* 5-Stage Drawer */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
  z-index: 9999;
  display: flex;
  justify-content: flex-end;
  animation: fadeIn 0.2s ease-out;
}
.drawer-panel {
  width: 820px;
  max-width: 95vw;
  height: 100vh;
  background: var(--bg-card, #ffffff);
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  animation: slideDrawer 0.25s ease-out;
}
@keyframes slideDrawer {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.drawer-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.drawer-close-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: transparent;
  border: none;
  font-size: 18px;
  color: #64748b;
  cursor: pointer;
}
.drawer-close-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
}
.drawer-content {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

/* 5 Stage Cards Grid */
.stage-cards-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.stage-card {
  padding: 12px 10px;
  border-radius: 10px;
  text-align: center;
  border: 1px solid transparent;
  transition: transform 0.15s ease;
}
.stage-card:hover {
  transform: translateY(-2px);
}
.stage-num {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 2px;
  opacity: 0.85;
}
.stage-title {
  font-size: 12.5px;
  font-weight: 700;
  margin-bottom: 6px;
}
.stage-count {
  font-size: 20px;
  font-weight: 800;
}
.stage-card.stage-1 { background: #eff6ff; border-color: #bfdbfe; color: #1e40af; }
.stage-card.stage-2 { background: #fef3c7; border-color: #fde68a; color: #92400e; }
.stage-card.stage-3 { background: #f3e8ff; border-color: #e9d5ff; color: #6b21a8; }
.stage-card.stage-4 { background: #e0e7ff; border-color: #c7d2fe; color: #3730a3; }
.stage-card.stage-5 { background: #dcfce7; border-color: #bbf7d0; color: #166534; }

.stage-detail-table th {
  background: #f8fafc;
  font-size: 12.5px;
  font-weight: 600;
  color: #475569;
  padding: 10px 12px;
}
.stage-detail-table td {
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
}
.stage-tag {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 600;
  background: #f1f5f9;
  color: #334155;
}
.badge-role-involved {
  font-size: 11.5px;
  padding: 3px 8px;
  border-radius: 4px;
  background: #e0f2fe;
  color: #0369a1;
  font-weight: 600;
}

/* ==========================================================================
   RBAC MATRIX STYLES
   ========================================================================== */
.tab-group-pills {
  display: flex;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 8px;
  gap: 4px;
}
.pill-tab {
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s ease;
}
.pill-tab.active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.role-selector-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.role-selector-label {
  font-weight: 700;
  font-size: 14px;
  color: #334155;
}
.role-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.role-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 20px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #334155;
  font-size: 13.5px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.role-pill-btn:hover {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
}
.role-pill-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
.role-code-tag {
  font-size: 11px;
  font-family: monospace;
  opacity: 0.85;
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.08);
}
.role-pill-btn.active .role-code-tag {
  background: rgba(255, 255, 255, 0.25);
}

.rbac-info-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  color: #1e40af;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 20px;
}
.rbac-info-box p {
  margin: 4px 0 0;
  color: #1e3a8a;
}

/* Switch Toggle UI */
.switch-toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.switch-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: #cbd5e1;
  transition: 0.2s;
  border-radius: 24px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.2s;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
input:checked + .slider {
  background-color: #2563eb;
}
input:focus + .slider {
  box-shadow: 0 0 1px #2563eb;
}
input:checked + .slider:before {
  transform: translateX(20px);
}
input:disabled + .slider {
  opacity: 0.45;
  cursor: not-allowed;
}

.th-toggle-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.th-toggle-header span {
  font-weight: 700;
  font-size: 12.5px;
}
.th-toggle-header small {
  font-size: 11px;
}

.module-title-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.module-order-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #f1f5f9;
  font-weight: 700;
  font-size: 12px;
  color: #475569;
}
.module-display-name {
  font-size: 14.5px;
  color: #0f172a;
}
.module-code-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.row-view-disabled td {
  background: #f8fafc;
  opacity: 0.65;
}

/* User Override Tab */
.user-override-header-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  background: #ffffff;
  padding: 16px 20px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.danger-text-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #dc2626;
  border-color: #fca5a5;
  padding: 8px 14px;
}
.danger-text-btn:hover {
  background: #fee2e2;
  color: #b91c1c;
}
.empty-user-select-box {
  text-align: center;
  padding: 4rem 2rem;
  background: #f8fafc;
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  margin-top: 20px;
}
.empty-user-select-box h3 {
  margin: 12px 0 6px;
  font-size: 16px;
  color: #334155;
}
.user-override-summary-badge {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 10px 16px;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 13px;
  color: #334155;
  margin-bottom: 16px;
}
.badge-override {
  font-size: 11px;
  background: #fef3c7;
  color: #b45309;
  border: 1px solid #fde68a;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 700;
}
''')
print("Appended Phase 4 CSS successfully!")

