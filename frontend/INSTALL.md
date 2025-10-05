# Installation Guide for AI DB Advisor Desktop

## Option 1: Full Tauri Installation (Requires Rust)

### Step 1: Install Rust

**Windows:**
1. Download Rust installer: https://rustup.rs/
2. Run `rustup-init.exe`
3. Follow the installer prompts (default options are fine)
4. Restart your terminal/IDE after installation

**Or use winget (Windows 11):**
```powershell
winget install Rustlang.Rustup
```

**Or use Chocolatey:**
```powershell
choco install rust
```

### Step 2: Install Visual C++ Build Tools (Windows only)

Download and install: https://visualstudio.microsoft.com/visual-cpp-build-tools/

Or install via Visual Studio Installer:
- Workload: "Desktop development with C++"

### Step 3: Verify Installation

```bash
cargo --version
rustc --version
```

### Step 4: Run the Application

```bash
cd tauri-app
npm install
npm run tauri:dev
```

---

## Option 2: Electron Alternative (No Rust Required)

I can create a lighter Electron version that doesn't require Rust. This will:
- ✅ Work immediately without Rust installation
- ✅ Support Windows, macOS, Linux
- ✅ Use the same API and React frontend
- ❌ Slightly larger bundle size (~200MB vs ~10MB)
- ❌ Slightly slower startup time

Would you like me to create an Electron version instead?

---

## Option 3: Web Application

The backend already has a web UI at:
```
http://127.0.0.1:8000/ui
```

You can use the web interface without installing the desktop app.

---

## Troubleshooting Tauri Installation

### Error: "cargo: command not found"
- Restart your terminal after installing Rust
- Add Rust to PATH: `%USERPROFILE%\.cargo\bin`

### Error: "linker 'link.exe' not found"
- Install Visual C++ Build Tools
- Restart terminal after installation

### Error: "failed to run custom build command for `tauri`"
- Update Rust: `rustup update`
- Clean and rebuild: `npm run tauri:build -- --clean`

### Error: "WebView2 not found" (Windows)
- Install WebView2 Runtime: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

---

## Quick Install Script (Windows PowerShell)

```powershell
# Install Rust
winget install Rustlang.Rustup

# Install Visual Studio Build Tools (requires manual interaction)
winget install Microsoft.VisualStudio.2022.BuildTools

# Restart terminal, then:
cd tauri-app
npm install
npm run tauri:dev
```

---

## macOS/Linux

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Restart terminal, then:
cd tauri-app
npm install
npm run tauri:dev
```

---

## Build Times

First build: ~10-15 minutes (Rust compiles dependencies)
Subsequent builds: ~1-2 minutes (incremental compilation)

---

## Alternative: Run as Web App

If you just want to test the functionality without desktop app:

1. Start the backend:
```bash
cd ..
python run.py
```

2. Open browser:
```
http://127.0.0.1:8000/ui
```

The web UI has all the same features as the desktop app!
