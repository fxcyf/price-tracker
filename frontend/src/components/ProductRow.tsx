import { useState } from "react";
import { Link } from "react-router-dom";
import { Trash2, ShoppingBag, TrendingDown, TrendingUp } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Product, deleteProduct } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface ProductRowProps {
  product: Product;
}

function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);
}

export default function ProductRow({ product }: ProductRowProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteMutation = useMutation({
    mutationFn: () => deleteProduct(product.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["facets"] });
      toast({ title: "Product removed" });
      setConfirmOpen(false);
    },
    onError: () => {
      toast({ title: "Failed to remove product", variant: "destructive" });
    },
  });

  const isOutOfStock = product.in_stock === false;
  const pct = product.price_change_pct;

  return (
    <>
      <div
        className={cn(
          "group flex items-center gap-3 rounded-lg border bg-card p-3 shadow-sm transition-shadow hover:shadow-md",
          isOutOfStock && "opacity-60 grayscale-[30%]"
        )}
      >
        {/* Thumbnail */}
        <Link to={`/products/${product.id}`} className="shrink-0">
          <div className="h-16 w-16 overflow-hidden rounded bg-muted">
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.title ?? "Product"}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center">
                <ShoppingBag className="h-6 w-6 text-muted-foreground/40" />
              </div>
            )}
          </div>
        </Link>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <Link
            to={`/products/${product.id}`}
            className="line-clamp-1 text-sm font-medium hover:underline"
          >
            {product.title ?? product.url}
          </Link>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {product.brand && <span>{product.brand}</span>}
            {product.brand && product.platform && product.platform !== "generic" && <span>·</span>}
            {product.platform && product.platform !== "generic" && (
              <span className="capitalize">{product.platform}</span>
            )}
            {product.in_stock === true && (
              <Badge className="h-4 bg-green-100 px-1.5 text-[10px] font-medium text-green-700 hover:bg-green-100">
                In stock
              </Badge>
            )}
            {product.in_stock === false && (
              <Badge className="h-4 bg-muted px-1.5 text-[10px] font-medium text-muted-foreground hover:bg-muted">
                Out of stock
              </Badge>
            )}
          </div>
          {/* Tags */}
          {product.tags.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {product.tags.map((tag) => (
                <Badge key={tag.id} variant="outline" className="text-[10px]">
                  {tag.name}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Price + change */}
        <div className="shrink-0 text-right">
          <p className="text-sm font-bold tabular-nums">
            {formatPrice(product.current_price, product.currency)}
          </p>
          {pct !== null && pct !== undefined && pct !== 0 && (
            <div
              className={cn(
                "mt-0.5 inline-flex items-center gap-0.5 text-[11px] font-semibold",
                pct < 0 ? "text-green-600" : "text-red-500"
              )}
            >
              {pct < 0 ? <TrendingDown className="h-3 w-3" /> : <TrendingUp className="h-3 w-3" />}
              {pct > 0 ? "+" : ""}{pct}%
            </div>
          )}
        </div>

        {/* Delete button */}
        <button
          onClick={() => setConfirmOpen(true)}
          className="shrink-0 rounded-full p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity hover:text-destructive"
          aria-label="Remove product"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remove product?</DialogTitle>
            <DialogDescription>
              This will delete the product and all its price history. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Removing…" : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
