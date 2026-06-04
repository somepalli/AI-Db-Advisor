import { useState } from 'react';

/**
 * Custom hook for persisting state in localStorage
 * @param key - localStorage key
 * @param initialValue - default value if key doesn't exist
 * @returns [storedValue, setValue] tuple
 */
export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((val: T) => T)) => void] {
  // Get initial value from localStorage or use initialValue
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  // Update localStorage when value changes
  const setValue = (value: T | ((val: T) => T)) => {
    try {
      // Allow value to be a function like useState
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  };

  return [storedValue, setValue];
}

/**
 * Custom hook for managing apply history in localStorage
 */
export function useApplyHistory() {
  const [history, setHistory] = useLocalStorage<any[]>('optimizer_apply_history', []);

  const addToHistory = (entry: any) => {
    setHistory((prev) => {
      const newHistory = [entry, ...prev];
      // Keep only last 100 entries
      return newHistory.slice(0, 100);
    });
  };

  const clearHistory = () => {
    setHistory([]);
  };

  return { history, addToHistory, clearHistory };
}
