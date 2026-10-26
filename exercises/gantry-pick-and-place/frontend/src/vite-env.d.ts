/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend RPC root, e.g. http://localhost:8000/rpc */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
