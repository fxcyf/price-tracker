# Frontend Scaffold

## Stack

| Package | Role |
|---|---|
| React 19 + Vite 6 | UI framework + dev server |
| React Router v7 | Client-side routing |
| TanStack Query v5 | Data fetching, caching, loading states |
| Axios | HTTP client |
| Tailwind CSS v3 | Utility-first styling |
| Shadcn/ui (manual) | Component library (Radix UI primitives + CVA) |
| Lucide React | Icons |
| Recharts | Price trend charts (used in detail page) |

## Key Files

| File | Role |
|---|---|
| `src/api/client.ts` | All typed API wrappers + TypeScript interfaces for backend schemas |
| `src/App.tsx` | QueryClient provider + BrowserRouter + route tree |
| `src/components/Layout.tsx` | Sidebar + `<Outlet />` shell |
| `src/components/ui/` | Shadcn components (written manually, no CLI needed) |
| `src/hooks/use-toast.ts` | Toast state management |
| `src/lib/utils.ts` | `cn()` helper — merges Tailwind classes |
| `src/index.css` | Tailwind directives + CSS variable palette |

## Dev server

```bash
cd frontend
npm run dev    # http://localhost:5173
```

Vite proxies `/api/*` to `http://localhost:8000` (configured in `vite.config.ts`),
so no CORS issues in development.

## Adding a new Shadcn component

Either write it manually in `src/components/ui/` following the same pattern (CVA + Radix primitive),
or run: `npx shadcn@latest add <component>` from the `frontend/` directory.

## Route Map

| Path | Component |
|---|---|
| `/` | `ProductListPage` |
| `/products/:id` | `ProductDetailPage` |
| `/settings` | `SettingsPage` |
