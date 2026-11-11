import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');

test('admin portal does not poll the employee-only AI maintenance status', () => {
  assert.match(source, /function useAiMaintenanceState\(enabled = true\)/);
  assert.match(source, /if \(!enabled\) return undefined;/);
  assert.match(source, /const aiStatus = useAiMaintenanceState\(portal === "client"\);/);
  assert.match(source, /\}, \[enabled\]\);\s*return aiStatus;/);
});
