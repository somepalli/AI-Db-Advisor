# AI DB Advisor Desktop Application

A cross-platform desktop application for AI-powered database performance analysis and optimization.

## Features

- **Data Source Management**: Register and manage multiple PostgreSQL database connections
- **Performance Dashboard**: Real-time metrics, top queries, and database locks
- **Query Analyzer**: Analyze SQL queries with EXPLAIN plans
- **Index Recommendations**: Get rule-based index suggestions with HypoPG validation
- **Query Rewrite Advice**: Identify anti-patterns and optimization opportunities
- **AI-Powered Suggestions**: Get intelligent recommendations from local LLM (Ollama)

## Prerequisites

1. **Backend API**: The FastAPI backend must be running on `http://127.0.0.1:8000`
   ```bash
   cd .venv/app
   python run.py
   ```

2. **Rust**: Required for building Tauri
   - Download from: https://www.rust-lang.org/tools/install
   - On Windows: Install Microsoft C++ Build Tools

3. **Node.js**: Version 16 or higher
   - Download from: https://nodejs.org/

## Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Development mode (with hot reload):
   ```bash
   npm run tauri:dev
   ```

3. Build for production:
   ```bash
   npm run tauri:build
   ```

## Building for Different Platforms

### Windows
```bash
npm run tauri:build
```
Output: `src-tauri/target/release/ai-db-advisor-desktop.exe`

### macOS
```bash
npm run tauri:build
```
Output: `src-tauri/target/release/bundle/macos/AI DB Advisor.app`

### Linux
```bash
npm run tauri:build
```
Output:
- `src-tauri/target/release/bundle/deb/ai-db-advisor-desktop_1.0.0_amd64.deb` (Debian/Ubuntu)
- `src-tauri/target/release/bundle/appimage/ai-db-advisor-desktop_1.0.0_amd64.AppImage` (AppImage)

## Cross-Platform Build Notes

### Building on Windows for other platforms:
- **For macOS**: Requires a Mac or macOS VM
- **For Linux**: Use WSL2 or a Linux VM

### Building on macOS:
- Can build for macOS
- Cannot build for Windows or Linux without VM

### Building on Linux:
- Can build for Linux
- Cannot build for Windows or macOS without VM

## Project Structure

```
tauri-app/
├── src/                    # React frontend
│   ├── api/               # API client
│   ├── components/        # React components
│   ├── types/             # TypeScript types
│   ├── App.tsx            # Main app component
│   └── main.tsx           # Entry point
├── src-tauri/             # Tauri backend
│   ├── src/
│   │   └── main.rs        # Rust main
│   ├── Cargo.toml         # Rust dependencies
│   └── tauri.conf.json    # Tauri configuration
├── package.json
└── vite.config.ts
```

## Configuration

The application is pre-configured to connect to `http://127.0.0.1:8000`. To change the API URL, edit:
- `src/api/client.ts` - Update `API_BASE_URL`
- `src-tauri/tauri.conf.json` - Update `http.scope`

## Usage

1. **Start Backend**:
   ```bash
   cd ../
   python run.py
   ```

2. **Launch Desktop App**:
   ```bash
   npm run tauri:dev
   ```

3. **Register Data Source**:
   - Click "Data Sources" in sidebar
   - Click "+ Add Data Source"
   - Enter ID, engine (postgres), and DSN
   - Click "Create Data Source"

4. **View Dashboard**:
   - Click on a registered data source
   - View database statistics, top queries, and locks

5. **Analyze Queries**:
   - Click "Query Analyzer" in sidebar
   - Paste your SQL query
   - Click "Analyze Query" for rule-based recommendations
   - Click "🤖 AI Analysis" for AI-powered suggestions

## Security

The application uses Tauri's security features:
- HTTP requests are scoped to `http://127.0.0.1:8000/**`
- No shell access except for opening URLs
- Sandboxed environment

## Icons

To customize icons:
1. Replace files in `src-tauri/icons/`
2. Required sizes: 32x32, 128x128, 128x128@2x
3. Formats: PNG for Windows/Linux, ICNS for macOS, ICO for Windows

## Troubleshooting

### "Failed to load data sources"
- Ensure the backend API is running on port 8000
- Check `http://127.0.0.1:8000/healthz` in browser

### Build fails on Windows
- Install Microsoft C++ Build Tools
- Ensure Rust is installed and in PATH

### "Command failed: cargo tauri build"
- Run `cargo clean` in `src-tauri` directory
- Delete `node_modules` and run `npm install` again

## License

Same as the parent AI DB Advisor project.

## Support

For issues, please check the main AI DB Advisor repository.
