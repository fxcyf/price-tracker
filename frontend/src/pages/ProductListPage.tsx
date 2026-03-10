import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, ShoppingBag, Trash2, X } from "lucide-react";
import { deleteTag, getProducts, getTags, type SortBy, type SortDir } from "@/api/client";
import ProductCard from "@/components/ProductCard";
import AddProductModal from "@/components/AddProductModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProductListPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [confirmDeleteTag, setConfirmDeleteTag] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>("date_added");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const queryClient = useQueryClient();

  const { data: allTags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: () => getTags().then((r) => r.data),
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

  const { data: products, isLoading, isError } = useQuery({
    queryKey: ["products", { category: categoryFilter || undefined, tag: activeTag ?? undefined, sort_by: sortBy, sort_dir: sortDir }],
    queryFn: () =>
      getProducts({
        category: categoryFilter || undefined,
        tag: activeTag ?? undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      }).then((r) => r.data),
  });

  function toggleTag(tag: string) {
    setActiveTag((prev) => (prev === tag ? null : tag));
  }

  return (
    <>
      <div className="flex flex-col">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background px-4">
          {/* Title — visible only on mobile since sidebar has it */}
          <h1 className="text-base font-semibold lg:hidden">Price Tracker</h1>
          <h1 className="hidden text-base font-semibold lg:block">Products</h1>
          <Button size="sm" onClick={() => setAddOpen(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Add Product</span>
            <span className="sm:hidden">Add</span>
          </Button>
        </div>

        {/* Filter bar */}
        <div className="border-b px-4 py-3 space-y-3">
          {/* Category text filter */}
          <div className="relative">
            <Input
              placeholder="Filter by category name…"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="pr-8 text-sm"
            />
            {categoryFilter && (
              <button
                onClick={() => setCategoryFilter("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Clear filter"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Sort controls */}
          <div className="flex items-center gap-2">
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
              {sortDir === "asc" ? (
                <ArrowUp className="h-3.5 w-3.5" />
              ) : (
                <ArrowDown className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>

          {/* Scrollable tag chips — only rendered when there are tags */}
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
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
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
              isFiltered={!!(categoryFilter || activeTag)}
              onAdd={() => setAddOpen(true)}
              onClear={() => {
                setCategoryFilter("");
                setActiveTag(null);
              }}
            />
          )}

          {!isLoading && !isError && products && products.length > 0 && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>

      <AddProductModal open={addOpen} onOpenChange={setAddOpen} />
    </>
  );
}

function SkeletonCard() {
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
            <p className="text-sm text-muted-foreground">Try adjusting the category or tag filters</p>
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
