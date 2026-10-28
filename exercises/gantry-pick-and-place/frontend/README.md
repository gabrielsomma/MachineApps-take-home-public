# Gantry dashboard (frontend)

React + TypeScript dashboard for the gantry pick-and-place backend. Setup, architecture and design notes are in the [exercise README](../README.md).

```bash
npm install
npm run dev      # regenerates the API client, then serves http://localhost:5173
npm run build    # type check + production build
npm run lint
```

- The typed API client in `src/gen/` is generated from `../backend/proto/app.proto` by `npm run gen` (Buf + protoc-gen-es, from `node_modules`). It runs automatically before `dev` and `build`, and is git-ignored.
- The backend URL defaults to `http://localhost:8000/rpc`. Override it with `VITE_API_URL` in a `.env.local` file.
