import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Pencil, ShoppingBag, X } from "lucide-react";
import { getProduct, getWatchConfig, getTags, updateProductTags, updateProductImage, suggestTags } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import CookieImportCard from "@/components/CookieImportCard";
import PriceChart from "@/components/PriceChart";
import WatchConfigCard from "@/components/WatchConfigCard";
import { TagInput } from "@/components/TagInput";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";

function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: product, isLoading: loadingProduct } = useQuery({
    queryKey: ["product", id],
    queryFn: () => getProduct(id!).then((r) => r.data),
    enabled: !!id,
  });

  const { data: watchConfig, isLoading: loadingWatch } = useQuery({
    queryKey: ["watch", id],
    queryFn: () => getWatchConfig(id!).then((r) => r.data),
    enabled: !!id,
  });

  const { data: allTags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: () => getTags().then((r) => r.data),
  });

  const tagMutation = useMutation({
    mutationFn: (tags: string[]) => updateProductTags(id!, tags).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["product", id], updated);
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast({ title: "Tags saved" });
    },
    onError: () => toast({ title: "Failed to save tags", variant: "destructive" }),
  });

  const [editingImage, setEditingImage] = useState(false);
  const [imageInputValue, setImageInputValue] = useState("");

  function startEditImage() {
    setImageInputValue(product?.image_url ?? "");
    setEditingImage(true);
  }

  function cancelEditImage() {
    setEditingImage(false);
    setImageInputValue("");
  }

  const imageMutation = useMutation({
    mutationFn: (url: string | null) => updateProductImage(id!, url).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["product", id], updated);
      setEditingImage(false);
      setImageInputValue("");
      toast({ title: "Image updated" });
    },
    onError: () => toast({ title: "Failed to update image", variant: "destructive" }),
  });

  const isLoading = loadingProduct || loadingWatch;

  return (
    <div className="flex flex-col">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 flex h-14 min-w-0 items-center gap-3 border-b bg-background px-4">
        <Link
          to="/"
          className="flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Back</span>
        </Link>

        {isLoading ? (
          <Skeleton className="h-4 w-48" />
        ) : (
          <p className="min-w-0 flex-1 truncate text-sm font-medium">
            {product?.title ?? product?.url ?? "Product"}
          </p>
        )}

        {product && (
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label="Open original product page"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>

      <div className="space-y-4 p-4">
        {/* Product hero */}
        {isLoading ? (
          <HeroSkeleton />
        ) : product ? (
          <div className="flex gap-4 rounded-lg border bg-card p-4">
            {/* Image */}
            <div className="shrink-0">
              {editingImage ? (
                <div className="flex w-24 flex-col gap-2 sm:w-32">
                  <div className="h-24 w-24 overflow-hidden rounded-md bg-muted sm:h-32 sm:w-32">
                    {imageInputValue ? (
                      <img
                        src={imageInputValue}
                        alt="Preview"
                        className="h-full w-full object-cover"
                        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <ShoppingBag className="h-8 w-8 text-muted-foreground/40" />
                      </div>
                    )}
                  </div>
                  <Input
                    type="url"
                    placeholder="https://…"
                    value={imageInputValue}
                    onChange={(e) => setImageInputValue(e.target.value)}
                    className="h-7 text-xs"
                    autoFocus
                  />
                  <div className="flex gap-1.5">
                    <Button
                      size="sm"
                      className="h-6 flex-1 text-xs"
                      onClick={() => imageMutation.mutate(imageInputValue.trim() || null)}
                      disabled={imageMutation.isPending}
                    >
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 px-2"
                      onClick={cancelEditImage}
                      disabled={imageMutation.isPending}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="group relative h-24 w-24 overflow-hidden rounded-md bg-muted sm:h-32 sm:w-32">
                  {product.image_url ? (
                    <img
                      src={product.image_url}
                      alt={product.title ?? "Product"}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center">
                      <ShoppingBag className="h-8 w-8 text-muted-foreground/40" />
                    </div>
                  )}
                  <button
                    onClick={startEditImage}
                    className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all group-hover:bg-black/40 group-hover:opacity-100"
                    aria-label="Edit image"
                  >
                    <Pencil className="h-5 w-5 text-white" />
                  </button>
                </div>
              )}
            </div>

            {/* Info */}
            <div className="min-w-0 flex-1 space-y-2">
              <h1 className="text-base font-semibold leading-snug sm:text-lg">
                {product.title ?? product.url}
              </h1>

              <p className="text-2xl font-bold tabular-nums">
                {formatPrice(product.current_price, product.currency)}
              </p>

              <div className="flex flex-wrap gap-1.5">
                {product.platform && product.platform !== "generic" && (
                  <Badge variant="secondary" className="capitalize">
                    {product.platform}
                  </Badge>
                )}
                {product.brand && (
                  <Badge variant="secondary">{product.brand}</Badge>
                )}
                {product.category && (
                  <Badge variant="outline">{product.category}</Badge>
                )}
              </div>

              <TagInput
                selected={product.tags.map((t) => t.name)}
                onChange={(tags) => tagMutation.mutate(tags)}
                suggestions={allTags}
                saving={tagMutation.isPending}
                onSuggest={() =>
                  suggestTags(id!).then((r) => r.data.suggested_tags)
                }
              />

              <p className="text-xs text-muted-foreground">
                Last updated: {formatDate(product.updated_at)}
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">
            <p>Product not found.</p>
            <Link to="/" className="mt-2 inline-block text-sm text-primary hover:underline">
              Return to list
            </Link>
          </div>
        )}

        {/* Price chart */}
        {id && product && (
          <PriceChart productId={id} currency={product.currency} />
        )}

        {/* Watch config */}
        {id && (
          <WatchConfigCard productId={id} initial={watchConfig} />
        )}

        {/* Cookie import */}
        {product && <CookieImportCard product={product} />}
      </div>
    </div>
  );
}

function HeroSkeleton() {
  return (
    <div className="flex gap-4 rounded-lg border bg-card p-4">
      <Skeleton className="h-24 w-24 shrink-0 rounded-md sm:h-32 sm:w-32" />
      <div className="flex-1 space-y-3">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="h-7 w-28" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-5 w-20" />
        </div>
        <Skeleton className="h-3 w-36" />
      </div>
    </div>
  );
}
