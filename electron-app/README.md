# AI DB Advisor - Electron Desktop App

A lightweight Electron wrapper for the AI DB Advisor web interface. **No Rust required!**

## ✨ Features

- ✅ **No Rust Installation Required** - Uses Electron (Node.js based)
- ✅ **Cross-Platform** - Windows, macOS, Linux
- ✅ **Quick Setup** - Install and run in 2 minutes
- ✅ **Full Feature Access** - All FastUI features available
- ✅ **Secure** - Restricts navigation to localhost only

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
cd electron-app
npm install
```

### Step 2: Start Backend

In a separate terminal:
```bash
cd ..
python run.py
```

Wait for: `Application startup complete`

### Step 3: Run Desktop App

```bash
npm start
```

That's it! The desktop app will open automatically.

## 📦 Building Installers

### Windows (.exe)
```bash
npm run build:win
```
Output: `dist/AI DB Advisor Setup 1.0.0.exe`

### macOS (.dmg)
```bash
npm run build:mac
```
Output: `dist/AI DB Advisor-1.0.0.dmg`

### Linux (.AppImage + .deb)
```bash
npm run build:linux
```
Output:
- `dist/AI DB Advisor-1.0.0.AppImage`
- `dist/ai-db-advisor-electron_1.0.0_amd64.deb`

## 📊 Comparison: Electron vs Tauri

| Feature | Electron | Tauri |
|---------|----------|-------|
| **Installation** | ✅ Node.js only | ❌ Requires Rust + C++ Build Tools |
| **Setup Time** | ⚡ 2 minutes | ⏱️ 30+ minutes |
| **Bundle Size** | 📦 ~150MB | 📦 ~10MB |
| **Startup Time** | 🐢 ~2 seconds | ⚡ <1 second |
| **Memory Usage** | 💾 ~150MB | 💾 ~50MB |
| **Cross-Platform** | ✅ Easy | ✅ Easy (after setup) |
| **First Build Time** | ⚡ 1 minute | ⏱️ 10-15 minutes |

## 🎯 Use This If:

- ✅ You want to get started immediately
- ✅ You don't have Rust installed
- ✅ Bundle size is not a major concern
- ✅ You're familiar with Node.js/Electron

## 🔧 Configuration

The app loads the web UI from `http://127.0.0.1:8000/ui`. To change this:

1. Edit `main.js`
2. Find: `mainWindow.loadURL('http://127.0.0.1:8000/ui')`
3. Change to your URL

## 📁 Project Structure

```
electron-app/
├── main.js          # Electron main process
├── error.html       # Error page when backend is down
├── package.json     # Dependencies and build config
└── README.md        # This file
```

## 🔒 Security Features

- Navigation restricted to localhost
- External links open in default browser
- No Node.js integration in renderer
- Context isolation enabled

## 🐛 Troubleshooting

### "Cannot connect to backend"
1. Make sure backend is running: `python run.py`
2. Check backend is accessible: Open `http://127.0.0.1:8000/ui` in browser
3. Click "Retry Connection" in the error page

### "electron: command not found"
```bash
npm install
```

### Build fails
```bash
# Clean and reinstall
rm -rf node_modules
npm install
npm run build
```

## 📦 Distribution

The built installers are standalone and include:
- Electron runtime
- Chromium browser engine
- Your application code

Users only need to:
1. Install the app
2. Run the Python backend
3. Open the desktop app

## 🔄 Auto-Updates

To add auto-updates, integrate with:
- [electron-updater](https://www.electron.build/auto-update)
- Deploy releases to GitHub/S3

## 💡 Tips

### Development Mode
```bash
NODE_ENV=development npm start
```
This enables DevTools automatically.

### Custom Icon
Replace these files (in root directory):
- `icon.ico` - Windows
- `icon.icns` - macOS
- `icon.png` - Linux (512x512)

### Reduce Bundle Size
1. Use `electron-builder` compression
2. Exclude unnecessary files in `package.json` build config
3. Use `asar` archives (enabled by default)

## 🆚 vs Tauri App

**Choose Electron if:**
- You want immediate deployment
- You're comfortable with larger bundle sizes
- You already know Electron

**Choose Tauri if:**
- You need minimal bundle size (<20MB)
- Performance is critical
- You can invest time in Rust setup

## 📝 License

Same as parent AI DB Advisor project.

## 🙋 Support

For issues, check the main AI DB Advisor documentation.
