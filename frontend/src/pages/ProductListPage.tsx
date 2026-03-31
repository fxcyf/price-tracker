import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Grid3X3,
  List,
  Package,
  Plus,
  Search,
  ShoppingBag,
  TrendingDown,
  Trash2,
  X,
} from "lucide-react";
import {
  deleteTag,
  getFacets,
  getProducts,
  getStats,
  getTags,
  type SortBy,
  type SortDir,
  type StockFilter,
} from "@/api/client";
import ProductCard from "@/components/ProductCard";
import ProductRow from "@/components/ProductRow";
import AddProductModal from "@/components/AddProductModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProductListPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [confirmDeleteTag, setConfirmDeleteTag] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>("date_added");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [stockFilter, setStockFilter] = useState<StockFilter>("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const queryClient = useQueryClient();

  const { data: allTags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: () => getTags().then((r) => r.data),
  });

  const { data: facets } = useQuery({
    queryKey: ["facets"],
    queryFn: () => getFacets().then((r) => r.data),
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => getStats().then((r) => r.data),
  });

  const deleteTagMutation = useMutation({
    mutationFn: (name: string) => deleteTag(name),
    onSuccess: (_data, name) => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      if (activeTag === name) setActiveTag(null);
      setConfirmDeleteTag(null);
    },
  });

  const inStockParam = stockFilter === "in_stock" ? true : stockFilter === "out_of_stock" ? false : undefined;

  const { data: products, isLoading, isError } = useQuery({
    queryKey: [
      "products",
      {
        q: searchQuery || undefined,
        tag: activeTag ?? undefined,
        brand: selectedBrand ?? undefined,
        platform: selectedPlatform ?? undefined,
        in_stock: inStockParam,
        sort_by: sortBy,
        sort_dir: sortDir,
      },
    ],
    queryFn: () =>
      getProducts({
        q: searchQuery || undefined,
        tag: activeTag ?? undefined,
        brand: selectedBrand ?? undefined,
        platform: selectedPlatform ?? undefined,
        in_stock: inStockParam,
        sort_by: sortBy,
        sort_dir: sortDir,
      }).then((r) => r.data),
  });

  const hasAnyFilter = !!(searchQuery || activeTag || selectedBrand || selectedPlatform || stockFilter !== "all");

  function clearAllFilters() {
    setSearchQuery("");
    setActiveTag(null);
    setSelectedBrand(null);
    setSelectedPlatform(null);
    setStockFilter("all");
  }

  function toggleTag(tag: string) {
    setActiveTag((prev) => (prev === tag ? null : tag));
  }

  return (
    <>
      <div className="flex flex-col">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background px-4">
          <h1 className="text-base font-semibold lg:hidden">Price Tracker v2</h1>
          <h1 className="hidden text-base font-semibold lg:block">Products</h1>
          <Button size="sm" onClick={() => setAddOpen(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Add Product</span>
            <span className="sm:hidden">Add</span>
          </Button>
        </div>

        {/* Stats bar */}
        {stats && stats.total > 0 && (
          <div className="flex items-center gap-4 border-b bg-muted/30 px-4 py-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Package className="h-3.5 w-3.5" />
              <span><span className="font-semibold text-foreground">{stats.total}</span> total</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShoppingBag className="h-3.5 w-3.5 text-green-600" />
              <span><span className="font-semibold text-foreground">{stats.in_stock}</span> in stock</span>
            </div>
            {stats.price_dropped_today > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <TrendingDown className="h-3.5 w-3.5 text-red-500" />
                <span><span className="font-semibold text-foreground">{stats.price_dropped_today}</span> dropped today</span>
              </div>
            )}
          </div>
        )}

        {/* Filter bar */}
        <div className="border-b px-4 py-3 space-y-3">
          {/* Global search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search title, brand, or category…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-8 text-sm"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Filter row: brand, platform, stock, sort, view toggle */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Brand filter */}
            {facets && facets.brands.length > 0 && (
              <select
                value={selectedBrand ?? ""}
                onChange={(e) => setSelectedBrand(e.target.value || null)}
                className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">All Brands</option>
                {facets.brands.map((b) => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
            )}

            {/* Platform filter */}
            {facets && facets.platforms.length > 1 && (
              <select
                value={selectedPlatform ?? ""}
                onChange={(e) => setSelectedPlatform(e.target.value || null)}
                className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">All Platforms</option>
                {facets.platforms.filter((p) => p !== "generic").map((p) => (
                  <option key={p} value={p} className="capitalize">{p}</option>
                ))}
              </select>
            )}

            {/* Stock filter — 3 state buttons */}
            <div className="inline-flex rounded-md border border-input shadow-sm">
              {(["all", "in_stock", "out_of_stock"] as StockFilter[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setStockFilter(v)}
                  className={`h-7 px-2 text-xs first:rounded-l-md last:rounded-r-md transition-colors ${
                    stockFilter === v
                      ? "bg-primary text-primary-foreground"
                      : "bg-background text-foreground hover:bg-muted"
                  }`}
                >
                  {v === "all" ? "All" : v === "in_stock" ? "In Stock" : "Out"}
                </button>
              ))}
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Sort controls */}
            <span className="shrink-0 text-xs font-medium text-muted-foreground">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="date_added">Date Added</option>
              <option value="price">Price</option>
              <option value="brand">Brand</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
              aria-label={sortDir === "asc" ? "Sort descending" : "Sort ascending"}
            >
              {sortDir === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />}
            </Button>

            {/* View toggle */}
            <div className="inline-flex rounded-md border border-input shadow-sm">
              <button
                onClick={() => setViewMode("grid")}
                className={`h-7 w-7 flex items-center justify-center rounded-l-md transition-colors ${
                  viewMode === "grid" ? "bg-primary text-primary-foreground" : "bg-background text-foreground hover:bg-muted"
                }`}
                aria-label="Grid view"
              >
                <Grid3X3 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={`h-7 w-7 flex items-center justify-center rounded-r-md transition-colors ${
                  viewMode === "list" ? "bg-primary text-primary-foreground" : "bg-background text-foreground hover:bg-muted"
                }`}
                aria-label="List view"
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Active filter tags — shows what's currently active, click to remove */}
          {hasAnyFilter && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Active:</span>
              {searchQuery && (
                <Badge variant="secondary" className="gap-1 text-xs cursor-pointer" onClick={() => setSearchQuery("")}>
                  search: {searchQuery} <X className="h-3 w-3" />
                </Badge>
              )}
              {selectedBrand && (
                <Badge variant="secondary" className="gap-1 text-xs cursor-pointer" onClick={() => setSelectedBrand(null)}>
                  brand: {selectedBrand} <X className="h-3 w-3" />
                </Badge>
              )}
              {selectedPlatform && (
                <Badge variant="secondary" className="gap-1 text-xs cursor-pointer" onClick={() => setSelectedPlatform(null)}>
                  platform: {selectedPlatform} <X className="h-3 w-3" />
                </Badge>
              )}
              {stockFilter !== "all" && (
                <Badge variant="secondary" className="gap-1 text-xs cursor-pointer" onClick={() => setStockFilter("all")}>
                  {stockFilter === "in_stock" ? "in stock" : "out of stock"} <X className="h-3 w-3" />
                </Badge>
              )}
              {activeTag && (
                <Badge variant="secondary" className="gap-1 text-xs cursor-pointer" onClick={() => setActiveTag(null)}>
                  tag: {activeTag} <X className="h-3 w-3" />
                </Badge>
              )}
              <button onClick={clearAllFilters} className="text-xs text-muted-foreground hover:text-foreground underline ml-1">
                Clear all
              </button>
            </div>
          )}

          {/* Scrollable tag chips */}
          {allTags.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
              <span className="shrink-0 text-xs font-medium text-muted-foreground">Tags:</span>
              {allTags.map((tag) =>
                confirmDeleteTag === tag ? (
                  <span
                    key={tag}
                    className="inline-flex shrink-0 items-center gap-1 rounded-full border border-destructive bg-destructive/10 px-2 py-0.5 text-xs text-destructive"
                  >
                    Delete "{tag}"?
                    <button
                      onClick={() => deleteTagMutation.mutate(tag)}
                      disabled={deleteTagMutation.isPending}
                      className="font-semibold hover:underline ml-1"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setConfirmDeleteTag(null)}
                      className="ml-0.5 text-destructive/60 hover:text-destructive"
                      aria-label="Cancel"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ) : (
                  <span key={tag} className="group relative shrink-0 inline-flex items-center">
                    <button onClick={() => toggleTag(tag)}>
                      <Badge
                        variant={activeTag === tag ? "default" : "outline"}
                        className="cursor-pointer capitalize transition-colors pr-5"
                      >
                        {tag}
                      </Badge>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setConfirmDeleteTag(tag); }}
                      className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                      aria-label={`Delete tag ${tag}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                )
              )}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4">
          {isLoading && (
            <div className={viewMode === "grid" ? "grid grid-cols-2 gap-3 lg:grid-cols-3" : "flex flex-col gap-2"}>
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} viewMode={viewMode} />
              ))}
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground">
              <p className="text-sm">Failed to load products. Is the backend running?</p>
              <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
                Retry
              </Button>
            </div>
          )}

          {!isLoading && !isError && products?.length === 0 && (
            <EmptyState
              isFiltered={hasAnyFilter}
              onAdd={() => setAddOpen(true)}
              onClear={clearAllFilters}
            />
          )}

          {!isLoading && !isError && products && products.length > 0 && viewMode === "grid" && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}

          {!isLoading && !isError && products && products.length > 0 && viewMode === "list" && (
            <div className="flex flex-col gap-2">
              {products.map((product) => (
                <ProductRow key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>

      <AddProductModal open={addOpen} onOpenChange={setAddOpen} />
    </>
  );
}

function SkeletonCard({ viewMode }: { viewMode: "grid" | "list" }) {
  if (viewMode === "list") {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
        <Skeleton className="h-16 w-16 shrink-0 rounded" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <Skeleton className="h-5 w-16" />
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Skeleton className="h-64 w-full sm:h-72" />
      <div className="space-y-1.5 p-2.5">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-5 w-16" />
      </div>
    </div>
  );
}

function EmptyState({
  isFiltered,
  onAdd,
  onClear,
}: {
  isFiltered: boolean;
  onAdd: () => void;
  onClear: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="rounded-full bg-muted p-4">
        <ShoppingBag className="h-8 w-8 text-muted-foreground" />
      </div>
      {isFiltered ? (
        <>
          <div>
            <p className="font-medium">No products match your filters</p>
            <p className="text-sm text-muted-foreground">Try adjusting the filters</p>
          </div>
          <Button variant="outline" size="sm" onClick={onClear}>
            Clear filters
          </Button>
        </>
      ) : (
        <>
          <div>
            <p className="font-medium">No products yet</p>
            <p className="text-sm text-muted-foreground">Start tracking prices by adding your first product</p>
          </div>
          <Button size="sm" onClick={onAdd} className="gap-1.5">
            <Plus className="h-4 w-4" />
            Add your first product
          </Button>
        </>
      )}
    </div>
  );
}
