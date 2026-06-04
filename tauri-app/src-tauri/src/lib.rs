// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use keyring::Entry;

const KEYRING_SERVICE: &str = "ai-db-advisor";

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// Store a secret (e.g. a database DSN) in the OS-native credential store.
#[tauri::command]
fn secret_set(key: String, value: String) -> Result<(), String> {
    let entry = Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    entry.set_password(&value).map_err(|e| e.to_string())
}

/// Retrieve a previously stored secret. Returns `None` if no entry exists.
#[tauri::command]
fn secret_get(key: String) -> Result<Option<String>, String> {
    let entry = Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

/// Delete a stored secret. Succeeds even if the entry does not exist.
#[tauri::command]
fn secret_delete(key: String) -> Result<(), String> {
    let entry = Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    match entry.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            secret_set,
            secret_get,
            secret_delete
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
