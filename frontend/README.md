# Project DJA: Frontend

React 19 + TypeScript + Vite client for the Project DJA advisor. See the
[root README](../README.md) for what the project does and how to run it.

```bash
npm ci
npm run dev      # http://localhost:5173, expects the API at http://localhost:8000
npm run lint
npm run build    # type-check and production build
```

Set `VITE_API_URL` to point at a different backend.

- `src/pages/`: intake (profile + transcript upload) and results
- `src/components/`: form steps, transcript review, compliance alert, course cards, Pell proration
- `src/api/client.ts`: typed calls to the backend, including 422 compliance errors
