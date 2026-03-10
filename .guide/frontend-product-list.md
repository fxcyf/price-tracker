# Frontend: Product List Page Patterns

## Responsive Layout Pattern

Two navigation variants, each toggled with Tailwind's `lg:` breakpoint:
- **Desktop**: `hidden lg:flex` sidebar with `<Outlet />` filling the remaining width
- **Mobile**: `lg:hidden` fixed bottom nav bar; main content gets `pb-16 lg:pb-0` to avoid overlap

```tsx
// Layout.tsx
<aside className="hidden lg:flex w-56 flex-col border-r bg-card">...</aside>
<main className="flex-1 overflow-auto pb-16 lg:pb-0"><Outlet /></main>
<nav className="fixed bottom-0 left-0 right-0 lg:hidden">...</nav>
```

## TanStack Query: Filtered + Sorted Queries

Include all filter and sort state in `queryKey`. TanStack Query re-fetches automatically when the key changes. Sort state follows the same pattern as filter state — just add more fields to the key object.

```typescript
const { data } = useQuery({
  queryKey: ["products", { category, tag, sort_by: sortBy, sort_dir: sortDir }],
  queryFn: () => getProducts({ category, tag, sort_by: sortBy, sort_dir: sortDir }).then(r => r.data),
});
```

Sort state is simple `useState` with typed values (use exported union types from `client.ts` to stay in sync with the API):

```typescript
const [sortBy, setSortBy] = useState<SortBy>("date_added");
const [sortDir, setSortDir] = useState<SortDir>("desc");
```

## Sorting UI: Native Select + Toggle Button

When shadcn/ui's `<Select>` component isn't installed, a styled native `<select>` matches the design system well. Use the same border/bg/ring Tailwind utilities as the `Input` component:

```tsx
<select
  value={sortBy}
  onChange={(e) => setSortBy(e.target.value as SortBy)}
  className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
>
  <option value="date_added">Date Added</option>
  <option value="price">Price</option>
  <option value="brand">Brand</option>
</select>
<Button variant="outline" size="sm" className="h-7 w-7 p-0"
  onClick={() => setSortDir(d => d === "asc" ? "desc" : "asc")}>
  {sortDir === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />}
</Button>
```

## useMutation + Cache Invalidation

After a mutation, call `queryClient.invalidateQueries` to mark stale and trigger refetch:

```typescript
const deleteMutation = useMutation({
  mutationFn: () => deleteProduct(product.id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["products"] });
    toast({ title: "Product removed" });
  },
});
```

## Two-Step Modal Pattern

For flows requiring a preview step (parse → confirm):
1. Keep step state and preview data in local modal component state
2. Use two separate `useMutation` instances
3. First mutation's `onSuccess` advances the step; second closes and resets

```typescript
const parseMutation = useMutation({
  mutationFn: (url: string) => parseUrl(url).then(r => r.data),
  onSuccess: (data) => { setPreview(data); setStep("preview"); },
});
const createMutation = useMutation({
  mutationFn: ({ url, tags }) => createProduct(url, tags).then(r => r.data),
  onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["products"] }); handleClose(); },
});
```

Reset modal state in `handleClose` using `setTimeout` to avoid flicker during close animation:
```typescript
function handleClose() {
  onOpenChange(false);
  setTimeout(() => { setStep("url"); setUrl(""); setPreview(null); parseMutation.reset(); }, 200);
}
```

## Skeleton Loading

Match the skeleton's shape to the real card to prevent layout shift:

```tsx
function SkeletonCard() {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Skeleton className="aspect-[4/3] w-full" />
      <div className="space-y-2 p-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-6 w-20" />
      </div>
    </div>
  );
}
```

## NavLink Active Styling

`NavLink` from react-router-dom provides `isActive` in the `className` callback:

```tsx
<NavLink
  to="/"
  end
  className={({ isActive }) =>
    cn("...", isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent")
  }
>
```

The `end` prop ensures `/` only matches exactly `/`, not all routes.
