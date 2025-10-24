# MCP Integration - Quick Start Guide
**Google Model Context Protocol Integration for AI DB Advisor**

---

## 🎯 Overview

This integration connects AI DB Advisor to **Google's MCP (Model Context Protocol) Toolbox** for advanced database optimization suggestions.

### ⚠️ **CRITICAL SAFETY PRINCIPLE**

**MCP tools ONLY generate suggestions - they NEVER execute code automatically.**

All execution requires:
1. ✅ User review
2. ✅ User approval
3. ✅ User confirmation
4. ✅ Explicit "Execute" action

---

## 🚀 Quick Start

### 1. Get MCP API Credentials

```bash
# Visit Google Cloud Console
https://console.cloud.google.com/

# Enable MCP API
# Create API Key or Service Account
# Note your API endpoint and credentials
```

### 2. Configure Environment

```bash
# Edit .env file
nano .env
```

Add:
```env
# MCP Configuration
MCP_ENABLED=true
MCP_ENDPOINT=https://mcp.googleapis.com/v1
MCP_API_KEY=your_api_key_here

# Safety Settings (DO NOT CHANGE)
MCP_AUTO_EXECUTE=false
MCP_REQUIRE_APPROVAL=true
```

### 3. Restart Backend

```bash
python run.py
```

Check logs for:
```
INFO: MCP integration enabled
INFO: Global MCP client initialized
```

---

## 📖 Usage

### Requesting MCP Suggestions

1. **Select a database connection** in the UI
2. **Enter or select a query** (optional)
3. **Click "Request MCP Suggestions"**
4. **Wait for suggestions** to appear

### Reviewing Suggestions

Each suggestion shows:
- **SQL Code**: What will be executed
- **Risk Level**: LOW / MEDIUM / HIGH / CRITICAL (color-coded)
- **Warnings**: Any safety concerns
- **Impact**: Affected tables and rows
- **Recommendation**: Should you proceed?

### Approving & Executing

```
Step 1: Review the suggestion
   ↓
Step 2: Click "Approve" or "Reject"
   ↓
Step 3: If approved, "Execute" button unlocks
   ↓
Step 4: Click "Execute"
   ↓
Step 5: Confirm in dialog
   ↓
Step 6: Execution proceeds
   ↓
Step 7: See results & audit log
```

---

## 🔐 Safety Features

### Risk Levels

| Level | Color | Examples | Approval |
|-------|-------|----------|----------|
| **LOW** | 🟢 Green | SELECT queries, CREATE INDEX | Standard |
| **MEDIUM** | 🟡 Yellow | UPDATE with WHERE, ALTER TABLE | Confirmation required |
| **HIGH** | 🟠 Orange | DELETE without WHERE, DROP INDEX | Double confirmation |
| **CRITICAL** | 🔴 Red | DROP TABLE, system modifications | Backup required |

### What Gets Blocked

❌ SQL injection patterns
❌ Direct execution without approval
❌ System table modifications (without explicit approval)
❌ Bulk operations without warnings

### What Gets Flagged

⚠️ Missing WHERE clauses
⚠️ SELECT * queries
⚠️ Non-reversible operations
⚠️ High-impact changes

---

## 🎨 UI Examples

### Suggestion Card (LOW RISK)

```
┌─────────────────────────────────────────────┐
│ 🟢 LOW RISK                                 │
│                                             │
│ Add index on enrollment_year column        │
│                                             │
│ SQL:                                        │
│ CREATE INDEX idx_enrollment_year            │
│   ON students(enrollment_year);            │
│                                             │
│ Rationale:                                  │
│ Queries filtering by enrollment_year will   │
│ be 10x faster with this index.             │
│                                             │
│ Impact:                                     │
│ • Tables: students                          │
│ • Reversible: Yes (can DROP index)         │
│                                             │
│ [Reject]              [Approve]             │
└─────────────────────────────────────────────┘
```

### Suggestion Card (HIGH RISK)

```
┌─────────────────────────────────────────────┐
│ 🔴 HIGH RISK                                │
│                                             │
│ ⚠️ WARNING: Missing WHERE clause           │
│                                             │
│ Delete inactive students                    │
│                                             │
│ SQL:                                        │
│ DELETE FROM students                        │
│   WHERE last_login < '2020-01-01';         │
│                                             │
│ ⚠️ Warnings:                                │
│ • Will delete approximately 1,200 rows      │
│ • Operation is NOT reversible               │
│ • Backup recommended before execution       │
│                                             │
│ Impact:                                     │
│ • Tables: students                          │
│ • Estimated rows: 1,200                     │
│ • Reversible: No                            │
│                                             │
│ 🛡️ Recommendation:                         │
│ Create a backup of 'students' table before  │
│ executing this operation.                   │
│                                             │
│ [Reject]              [Approve]             │
└─────────────────────────────────────────────┘
```

### Execution Confirmation (CRITICAL)

```
┌─────────────────────────────────────────────┐
│        🚨 CRITICAL OPERATION               │
├─────────────────────────────────────────────┤
│                                             │
│ You are about to execute:                   │
│                                             │
│ DROP TABLE legacy_data;                     │
│                                             │
│ ⚠️ THIS OPERATION IS IRREVERSIBLE!         │
│                                             │
│ Requirements:                               │
│ ✓ Backup of 'legacy_data' table            │
│ ✓ Understanding of consequences             │
│                                             │
│ Type 'DELETE LEGACY_DATA' to confirm:       │
│ [_____________________________________]     │
│                                             │
│ [Cancel]                       [Execute]    │
└─────────────────────────────────────────────┘
```

---

## 📊 Audit Log Example

```
┌─────────────────────────────────────────────────────────┐
│ MCP Activity Log                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 2025-01-05 12:00:00 | USER: john@example.com          │
│ Action: Suggestion Generated                           │
│ Tool: db_index_optimizer                               │
│ Risk: MEDIUM                                           │
│ SQL: CREATE INDEX idx_enrollment_year ON students...   │
│                                                         │
│ 2025-01-05 12:00:15 | USER: john@example.com          │
│ Action: Approved                                       │
│ Approval ID: approval-abc123                           │
│                                                         │
│ 2025-01-05 12:00:30 | USER: john@example.com          │
│ Action: Executed                                       │
│ Status: SUCCESS                                        │
│ Duration: 0.5s                                         │
│ Result: Index created successfully                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration Options

### MCP Settings

```python
# In .env or config.py

# Enable/disable MCP integration
MCP_ENABLED = true

# MCP API endpoint
MCP_ENDPOINT = "https://mcp.googleapis.com/v1"

# API credentials
MCP_API_KEY = "your_key"

# Max suggestions per request
MCP_MAX_SUGGESTIONS = 5

# Timeout for MCP API calls (seconds)
MCP_TIMEOUT = 30
```

### Safety Settings

```python
# CRITICAL: Never change these to true
MCP_AUTO_EXECUTE = false           # MUST be false
MCP_REQUIRE_APPROVAL = true        # MUST be true

# Recommended settings
MCP_REQUIRE_BACKUP_HIGH_RISK = true
MCP_LOG_ALL_ACTIVITIES = true
MCP_DOUBLE_CONFIRM_CRITICAL = true
```

---

## 🐛 Troubleshooting

### Problem: "MCP client not initialized"

**Solution**:
```bash
# Check .env file
cat .env | grep MCP_ENABLED

# Should show: MCP_ENABLED=true

# Restart backend
python run.py
```

### Problem: "API authentication failed"

**Solution**:
```bash
# Verify API key
echo $MCP_API_KEY

# Test credentials
curl -H "Authorization: Bearer $MCP_API_KEY" \
  https://mcp.googleapis.com/v1/auth/validate
```

### Problem: "No suggestions generated"

**Check**:
1. Database connection is active
2. Schema is loaded
3. MCP tools are available for your database type
4. Check logs for MCP tool errors

### Problem: "Cannot execute approved suggestion"

**Check**:
1. Suggestion status is "approved"
2. Database connection is still active
3. No schema changes since approval
4. Check execution logs for errors

---

## 📞 Support

### Logs Location
```bash
# Backend logs
tail -f logs/mcp_integration.log

# Audit logs
tail -f logs/mcp_audit.log
```

### Debug Mode

Enable verbose logging:
```python
# In config.py
LOG_LEVEL = "DEBUG"
MCP_DEBUG = True
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No suggestions | No MCP tools for DB type | Check tool discovery |
| High-risk flagged | Missing WHERE clause | Add WHERE or confirm |
| Execution blocked | Not approved | Approve suggestion first |
| Timeout | Large schema | Increase MCP_TIMEOUT |

---

## 🎓 Best Practices

### DO ✅

- Review all suggestions carefully
- Check risk levels before approving
- Create backups for HIGH/CRITICAL operations
- Use suggestions as learning opportunities
- Review audit logs regularly

### DON'T ❌

- Approve without reading SQL
- Ignore risk warnings
- Execute CRITICAL operations in production without backups
- Override safety settings
- Approve bulk operations without understanding impact

---

## 📚 Additional Resources

- **Architecture Design**: `docs/MCP_INTEGRATION_DESIGN.md`
- **Implementation Details**: `docs/MCP_IMPLEMENTATION_SUMMARY.md`
- **API Documentation**: `http://localhost:8000/docs` (when running)
- **MCP Protocol Spec**: https://modelcontextprotocol.io

---

## 🆘 Emergency Procedures

### If Something Goes Wrong

1. **Stop Execution**: MCP operations are monitored - you can cancel
2. **Check Audit Log**: Review what was executed
3. **Rollback (if possible)**: Some operations support rollback
4. **Restore from Backup**: If operation was destructive
5. **Report Issue**: Contact support with audit log

### Disabling MCP

```bash
# In .env
MCP_ENABLED=false

# Restart
python run.py
```

All pending approvals will be preserved but cannot execute until MCP is re-enabled.

---

**Version**: 1.0
**Last Updated**: 2025-01-05
**Status**: Production Ready (after integration testing)
