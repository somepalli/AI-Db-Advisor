# End-to-End Test Plan for Alert System in Tauri App

## Overview

This document outlines the manual and automated E2E tests for the Alert System integrated into the Tauri desktop application.

## Test Environment Setup

### Prerequisites
1. Backend running: `python run.py` (http://127.0.0.1:8000)
2. Frontend running: `npm run tauri dev` or `npm run dev`
3. At least one datasource configured (PostgreSQL recommended)
4. Ollama running for AI analysis (optional but recommended)

### Test Data Setup
```bash
# Add a test PostgreSQL datasource
curl -X POST http://127.0.0.1:8000/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-postgres",
    "engine": "postgres",
    "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
  }'
```

---

## Test Suite 1: Alert Panel Navigation & UI

### Test 1.1: Navigate to Alerts View
**Steps:**
1. Launch Tauri app
2. Click "🔔 Alerts" button in header
3. Verify Alerts view is displayed

**Expected:**
- Alerts panel loads successfully
- Header shows "🚨 Database Alerts" title
- "Active Alerts" and "Alert History" tabs visible
- Auto-refresh toggle visible (default: ON)
- "⚙️ Manage Rules" button visible

**Status:** ☐ Pass ☐ Fail

---

### Test 1.2: Alert Panel Auto-Refresh
**Steps:**
1. Navigate to Alerts view
2. Observe auto-refresh indicator (every 30s)
3. Toggle auto-refresh OFF
4. Verify refresh stops
5. Toggle auto-refresh ON
6. Verify refresh resumes

**Expected:**
- Auto-refresh works every 30 seconds when enabled
- Toggle correctly stops/starts refresh
- UI shows loading state during refresh

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 2: Alert Triggering & Display

### Test 2.1: View Active Alerts (Empty State)
**Steps:**
1. Navigate to Alerts view
2. Click "Active Alerts" tab
3. Verify empty state message

**Expected:**
- Shows "No active alerts" message
- Displays green checkmark icon
- Message: "All systems operating normally"

**Status:** ☐ Pass ☐ Fail

---

### Test 2.2: Trigger P1 Critical Alert
**Steps:**
1. Start monitoring for test-postgres datasource via API:
   ```bash
   curl -X POST http://127.0.0.1:8000/alerts/monitoring/test-postgres/start
   ```
2. Wait for alert to trigger (monitoring evaluates every 60s)
3. Check Alerts panel for new alert

**Expected:**
- P1 alert appears in "Active Alerts" tab
- Red background color
- Shows severity, title, message, timestamp
- "🔍 Analyze with AI" button visible
- "✓ Acknowledge" button visible

**Status:** ☐ Pass ☐ Fail

---

### Test 2.3: Alert Severity Color Coding
**Steps:**
1. Verify alerts are displayed with correct colors:
   - P1 (Critical): Red background (#fee2e2)
   - P2 (High): Orange background (#fed7aa)
   - P3 (Medium): Yellow background (#fef3c7)

**Expected:**
- Each severity level has distinct color
- Color is easily distinguishable
- Text remains readable on colored background

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 3: AI Analysis Integration

### Test 3.1: Request AI Analysis
**Steps:**
1. Trigger an alert (see Test 2.2)
2. Click "🔍 Analyze with AI" button
3. Wait for analysis to complete

**Expected:**
- Loading indicator appears
- AI analysis modal opens
- Shows root cause explanation
- Lists 3+ immediate actions
- Displays recommendations with:
  - Type (config/index/query/action)
  - Summary
  - Rationale
  - SQL/Command (if applicable)
  - Risk level
  - Expected improvement

**Status:** ☐ Pass ☐ Fail

---

### Test 3.2: AI Analysis Error Handling
**Steps:**
1. Stop Ollama service
2. Trigger an alert
3. Click "🔍 Analyze with AI"
4. Verify fallback behavior

**Expected:**
- Falls back to rule-based analysis
- Shows lower confidence score (0.5)
- Displays at least 1 recommendation
- Error message if AI completely unavailable

**Status:** ☐ Pass ☐ Fail

---

### Test 3.3: Close AI Analysis Modal
**Steps:**
1. Open AI analysis (see Test 3.1)
2. Click "✕ Close" button
3. Verify modal closes

**Expected:**
- Modal closes smoothly
- Returns to alerts list
- Alert still shows in list

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 4: Alert Acknowledgment

### Test 4.1: Acknowledge Alert with Note
**Steps:**
1. Click "✓ Acknowledge" on an active alert
2. Enter name: "Test DBA"
3. Enter note: "Investigating disk space issue"
4. Click "Acknowledge"

**Expected:**
- Alert moves to "Acknowledged" status
- Shows acknowledged by "Test DBA"
- Shows acknowledgment note
- Timestamp updated
- "Resolve" button now visible

**Status:** ☐ Pass ☐ Fail

---

### Test 4.2: Acknowledge Without Note
**Steps:**
1. Click "✓ Acknowledge" on alert
2. Enter name only
3. Leave note blank
4. Click "Acknowledge"

**Expected:**
- Acknowledgment succeeds
- Note field optional
- Status updates correctly

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 5: Alert Resolution

### Test 5.1: Manual Resolution
**Steps:**
1. Acknowledge an alert (see Test 4.1)
2. Click "Resolve" button
3. Enter resolution note: "Cleared old logs, freed 50GB"
4. Click "Resolve"

**Expected:**
- Alert status changes to "Resolved"
- Alert moves to "Alert History" tab
- Resolution note saved
- Resolved timestamp recorded
- Green checkmark indicator shows

**Status:** ☐ Pass ☐ Fail

---

### Test 5.2: Auto-Resolution
**Steps:**
1. Wait for alert condition to clear (metric returns to normal)
2. Wait for next monitoring cycle (60s)
3. Check alert status

**Expected:**
- Alert automatically resolves
- Status shows "Auto-Resolved"
- Appears in "Alert History"
- Green badge shows "Auto-Resolved"

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 6: Alert History

### Test 6.1: View Alert History
**Steps:**
1. Navigate to "Alert History" tab
2. Verify resolved alerts appear

**Expected:**
- Shows all resolved/auto-resolved alerts
- Sorted by resolved time (newest first)
- Each alert shows:
  - Original severity
  - Title and message
  - Triggered time
  - Resolved time
  - Resolution method (manual/auto)
  - Resolution note (if manual)

**Status:** ☐ Pass ☐ Fail

---

### Test 6.2: Filter History by Severity
**Steps:**
1. In Alert History tab
2. Click severity filter buttons (P1/P2/P3)
3. Verify filtering works

**Expected:**
- "All" button shows all alerts
- P1/P2/P3 buttons filter correctly
- Active filter button highlighted
- Count updates in real-time

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 7: Alert Rules Management

### Test 7.1: View All Rules
**Steps:**
1. Click "⚙️ Manage Rules" button
2. Verify rules list appears

**Expected:**
- Modal opens with all 16 default rules
- Each rule shows:
  - Name and ID
  - Severity badge
  - Description
  - Conditions
  - Cooldown period
  - Applicable database types

**Status:** ☐ Pass ☐ Fail

---

### Test 7.2: Create Custom Rule
**Steps:**
1. Open Manage Rules modal
2. Click "➕ Add Custom Rule"
3. Fill in rule details:
   - Name: "Test Custom Rule"
   - Severity: P2
   - Metric: cpu_percent
   - Operator: >
   - Threshold: 90
4. Click "Create Rule"

**Expected:**
- Rule created successfully
- Appears in rules list
- Can be used in monitoring
- Validates required fields

**Status:** ☐ Pass ☐ Fail

---

### Test 7.3: Delete Custom Rule
**Steps:**
1. Create a custom rule (see Test 7.2)
2. Click "🗑️ Delete" button
3. Confirm deletion

**Expected:**
- Confirmation dialog appears
- After confirm, rule removed
- Cannot delete default rules
- Custom rules can be deleted

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 8: Multi-Datasource Alerts

### Test 8.1: Alerts from Multiple Datasources
**Steps:**
1. Configure 2+ datasources
2. Start monitoring for all
3. Trigger alerts on both
4. View alerts panel

**Expected:**
- Alerts from all datasources appear
- Each alert shows datasource ID
- Can filter by datasource
- No conflicts between datasources

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 9: Error Handling

### Test 9.1: Backend Unavailable
**Steps:**
1. Stop backend server
2. Navigate to Alerts view
3. Observe error handling

**Expected:**
- Friendly error message displayed
- "Retry" button available
- No app crash
- Graceful degradation

**Status:** ☐ Pass ☐ Fail

---

### Test 9.2: Invalid Datasource
**Steps:**
1. Start monitoring for non-existent datasource
2. Observe error handling

**Expected:**
- Error message displayed
- Other datasources continue working
- No cascade failures

**Status:** ☐ Pass ☐ Fail

---

## Test Suite 10: Performance & Usability

### Test 10.1: Large Alert Volume
**Steps:**
1. Trigger 50+ alerts
2. Navigate to Alerts view
3. Test scrolling and filtering

**Expected:**
- UI remains responsive
- Scrolling is smooth
- Filtering works with large datasets
- No memory leaks

**Status:** ☐ Pass ☐ Fail

---

### Test 10.2: Real-Time Updates
**Steps:**
1. Have Alerts view open
2. Trigger new alert via API
3. Wait for auto-refresh (30s)

**Expected:**
- New alert appears without manual refresh
- Auto-refresh doesn't disrupt user interaction
- Scroll position maintained (if not viewing new alerts)

**Status:** ☐ Pass ☐ Fail

---

## Automated E2E Tests (Future - Playwright)

### Setup
```bash
cd tauri-app
npm install -D @playwright/test
npx playwright install
```

### Sample Test Structure
```typescript
// tests/e2e/alerts.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Alert System E2E', () => {
  test('should navigate to alerts view', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('button:has-text("🔔 Alerts")');
    await expect(page.locator('h2:has-text("Database Alerts")')).toBeVisible();
  });

  test('should display active alerts', async ({ page }) => {
    // ... test implementation
  });
});
```

---

## Test Execution Checklist

**Pre-Flight:**
- [ ] Backend running and healthy
- [ ] Frontend running
- [ ] Test datasource configured
- [ ] Ollama running (for AI tests)

**Execution:**
- [ ] All Suite 1 tests passed
- [ ] All Suite 2 tests passed
- [ ] All Suite 3 tests passed
- [ ] All Suite 4 tests passed
- [ ] All Suite 5 tests passed
- [ ] All Suite 6 tests passed
- [ ] All Suite 7 tests passed
- [ ] All Suite 8 tests passed
- [ ] All Suite 9 tests passed
- [ ] All Suite 10 tests passed

**Post-Flight:**
- [ ] All critical bugs documented
- [ ] Performance issues noted
- [ ] UX improvements identified

---

## Bug Tracking Template

**Bug ID:** E2E-XXX
**Test:** [Test Suite X.Y]
**Severity:** Critical / High / Medium / Low
**Description:** [What went wrong]
**Steps to Reproduce:**
1. ...
2. ...

**Expected:** [What should happen]
**Actual:** [What actually happened]
**Screenshots:** [If applicable]
**Logs:** [Console errors, backend logs]

---

## Success Criteria

**MVP (Minimum Viable Product):**
- ✅ 80%+ of critical tests passing
- ✅ No P1 bugs blocking core functionality
- ✅ All 3 alert lifecycles work (trigger → acknowledge → resolve)
- ✅ AI analysis functional (or graceful fallback)

**Production Ready:**
- ✅ 95%+ of all tests passing
- ✅ Zero P1/P2 bugs
- ✅ Performance tests passing
- ✅ Error handling validated
- ✅ Multi-datasource support working

---

## Notes

- Some tests require manual triggering of alerts via metrics
- AI tests may vary based on LLM availability
- Auto-refresh timing may need adjustment based on performance
- Consider adding screenshot comparisons for visual regression testing
