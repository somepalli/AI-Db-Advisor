# Security Remediation — Secret Purge & Rotation

This repository previously committed real credentials. They have been removed from the
**current** working tree, but they still exist in **git history** until the steps below are
run. Treat every value listed here as compromised.

## 1. Rotate the exposed credentials (do this FIRST — they are public)

- [ ] **Google API key** `AIzaSyD6VA6doaEnnG8MCQJrGL8Brxtvwu6LZLU`
      → Revoke/regenerate in Google Cloud Console → APIs & Services → Credentials.
      Update your local `.env` as `MCP_API_KEY=<new-key>`.
- [ ] **ClickHouse Toolbox reader password** `ToolboxReader#2025`
      → Change the ClickHouse user's password; set `TOOLBOX_CLICKHOUSE_PASSWORD` in
      `.env.clickhouse` / `.env.toolbox`.
- [ ] **Toolbox API key** `toolbox-local-key`
      → Generate a strong random value; set `TOOLBOX_API_KEY`.

Rotating first means that even though the old values remain in any existing clones/forks,
they no longer grant access.

## 2. Purge the values from git history

Use [`git filter-repo`](https://github.com/newren/git-filter-repo) (preferred over BFG).
Run from a fresh clone with no uncommitted work:

```bash
pip install git-filter-repo

# Remove the leaked files from all of history
git filter-repo --invert-paths \
  --path .env.clickhouse \
  --path .env.toolbox

# Scrub leaked string values from all remaining blobs
cat > /tmp/secrets.txt <<'EOF'
AIzaSyD6VA6doaEnnG8MCQJrGL8Brxtvwu6LZLU==>REDACTED
ToolboxReader#2025==>REDACTED
toolbox-local-key==>REDACTED
265943271765==>REDACTED
EOF
git filter-repo --replace-text /tmp/secrets.txt
```

## 3. Force-push and invalidate old clones

```bash
git remote add origin <your-remote-url>   # filter-repo drops the remote
git push --force --all
git push --force --tags
```

> ⚠️ This rewrites history. Everyone with a clone must re-clone. Existing forks/PRs will
> still contain the old commits — that is why step 1 (rotation) is mandatory.

## 4. Verify

```bash
git log -p --all | grep -E "AIzaSy|ToolboxReader#2025|toolbox-local-key|265943271765"   # → no output
git ls-files | grep -E "^\.env\.(clickhouse|toolbox)$"                                   # → no output
```

## Going forward

- Real `.env*` files are git-ignored (only `*.example` templates are tracked).
- No secrets in source defaults — code reads them from the environment and fails fast if missing.
