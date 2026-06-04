/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the AI DB Advisor backend API. Defaults to http://127.0.0.1:8095. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
