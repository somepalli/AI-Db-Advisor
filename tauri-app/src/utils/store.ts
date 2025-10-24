// Simple localStorage-based store for persisting database connections
// In a full Tauri implementation, you could use @tauri-apps/plugin-store

export interface StoredConnection {
  id: string;
  engine: string;
  dsn: string;
  createdAt: string;
}

const STORAGE_KEY = 'ai-db-advisor-connections';

export const connectionStore = {
  // Get all saved connections
  getAll: (): StoredConnection[] => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Failed to load connections:', error);
      return [];
    }
  },

  // Save a new connection
  save: (connection: Omit<StoredConnection, 'createdAt'>): void => {
    try {
      const connections = connectionStore.getAll();
      const newConnection: StoredConnection = {
        ...connection,
        createdAt: new Date().toISOString(),
      };

      // Check if connection with this ID already exists
      const existingIndex = connections.findIndex(c => c.id === connection.id);
      if (existingIndex >= 0) {
        // Update existing connection
        connections[existingIndex] = newConnection;
      } else {
        // Add new connection
        connections.push(newConnection);
      }

      localStorage.setItem(STORAGE_KEY, JSON.stringify(connections));
    } catch (error) {
      console.error('Failed to save connection:', error);
      throw new Error('Failed to save connection to storage');
    }
  },

  // Delete a connection by ID
  delete: (id: string): void => {
    try {
      const connections = connectionStore.getAll();
      const filtered = connections.filter(c => c.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    } catch (error) {
      console.error('Failed to delete connection:', error);
      throw new Error('Failed to delete connection from storage');
    }
  },

  // Get a specific connection by ID
  getById: (id: string): StoredConnection | null => {
    const connections = connectionStore.getAll();
    return connections.find(c => c.id === id) || null;
  },

  // Clear all connections
  clear: (): void => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error('Failed to clear connections:', error);
    }
  },
};
