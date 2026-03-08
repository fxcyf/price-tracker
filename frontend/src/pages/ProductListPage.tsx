import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, ShoppingBag, X } from "lucide-react";
import { getProducts } from "@/api/client";
import ProductCard from "@/components/ProductCard";
import AddProductModal from "@/components/AddProductModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const PRESET_TAGS = ["sale", "wishlist", "electronics", "clothing", "shoes", "home"];

export default function ProductListPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const { data: products, isLoading, isError } = useQuery({
    queryKey: ["products", { category: categoryFilter || undefined, tag: activeTag ?? undefined }],
    queryFn: () =>
      getProducts({
        category: categoryFilter || undefined,
        tag: activeTag ?? undefined,
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
              placeholder="Filter by category…"
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

          {/* Scrollable tag chips */}
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
            {PRESET_TAGS.map((tag) => (
              <button key={tag} onClick={() => toggleTag(tag)} className="shrink-0">
                <Badge
                  variant={activeTag === tag ? "default" : "outline"}
                  className="cursor-pointer capitalize transition-colors"
                >
                  {tag}
                </Badge>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          {isLoading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
      <Skeleton className="aspect-[4/3] w-full" />
      <div className="space-y-2 p-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-6 w-20" />
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
