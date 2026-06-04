# Google MCP/Gemini API Setup Guide

> **Scope:** MCP integration currently targets **PostgreSQL only**. When MCP is not
> configured (`MCP_ENABLED=false`), the UI runs in **demo mode** and shows illustrative
> sample suggestions, clearly labelled in the MCP panel.

## Current Status

Set your API key in `.env` as `MCP_API_KEY` (never commit it). See `.env.example`.
❌ **Issue Found**: The "MCP" endpoint doesn't exist - this needs to be clarified

## Important Findings

After testing your API key, here's what I discovered:

### 1. The API Key is Valid
- The API key works with Google APIs
- Project ID: `<YOUR_GOOGLE_CLOUD_PROJECT_ID>`

### 2. MCP Endpoint Issue
The endpoint `https://mcp.googleapis.com/v1` **does not exist**.

**What is "Google MCP"?**
There are two possibilities:

#### Option A: You meant **Gemini API** (Google's AI model)
If you want to use Google's Gemini AI model for database suggestions:

**Required Action:**
1. Enable the Generative Language API in your Google Cloud project
2. Visit: https://console.developers.google.com/apis/api/generativelanguage.googleapis.com/overview?project=<YOUR_GOOGLE_CLOUD_PROJECT_ID>
3. Click "Enable"

**API Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models`

#### Option B: You meant **Model Context Protocol (MCP)**
MCP is an open-source protocol by Anthropic, not a Google service. If you want to use MCP:

**Options:**
1. **Use our demo mode** (currently implemented) - generates mock suggestions
2. **Host your own MCP server** - requires setting up an MCP-compatible server
3. **Use a third-party MCP provider** - requires finding and configuring a provider

## Recommendation

Since you mentioned "Google MCP Toolbox", I believe you might be referring to one of these:

### If you want AI-powered suggestions (Recommended):

**Use Gemini API:**
1. Enable Generative Language API (link above)
2. Update `.env`:
   ```env
   # Change this:
   MCP_ENDPOINT=https://mcp.googleapis.com/v1

   # To this:
   GEMINI_ENDPOINT=https://generativelanguage.googleapis.com/v1beta
   ```

3. I can update the code to use Gemini instead of MCP

### If you want to keep demo mode:

Your current setup works fine with **demo MCP suggestions**. The AI chat feature generates realistic-looking suggestions without actually calling any external API.

## What Should We Do?

Please clarify what you'd like:

**Option 1**: Enable Gemini API and I'll integrate it ✨
- Real AI-powered suggestions
- Uses your Google API key
- Requires enabling the API

**Option 2**: Keep demo mode 🎭
- Works now without changes
- Generates mock suggestions
- Good for testing/development

**Option 3**: Set up real MCP server 🔧
- More complex setup
- Need to host or find MCP provider
- Not a Google service

---

## Current Configuration Status

```
✅ .env file created
✅ API key configured
✅ MCP client code updated
⚠️  Endpoint needs correction
```

## Next Steps

1. **Let me know which option you prefer**
2. **If Gemini API**: Enable it in Google Cloud Console
3. **I'll update the code** accordingly
4. **Test the integration** to confirm it works

