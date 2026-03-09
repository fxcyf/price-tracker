import { useState } from "react";
import { Link } from "react-router-dom";
import { Trash2, ShoppingBag } from "lucide-react";
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

interface ProductCardProps {
  product: Product;
}

function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);
}

export default function ProductCard({ product }: ProductCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteMutation = useMutation({
    mutationFn: () => deleteProduct(product.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast({ title: "Product removed" });
      setConfirmOpen(false);
    },
    onError: () => {
      toast({ title: "Failed to remove product", variant: "destructive" });
    },
  });

  return (
    <>
      <div className="group relative flex flex-col overflow-hidden rounded-lg border bg-card shadow-sm transition-shadow hover:shadow-md">
        {/* Delete button — top-right corner, appears on hover (always visible on mobile) */}
        <button
          onClick={(e) => {
            e.preventDefault();
            setConfirmOpen(true);
          }}
          className={cn(
            "absolute right-2 top-2 z-10 rounded-full bg-background/80 p-1.5 text-muted-foreground backdrop-blur-sm transition-opacity",
            "opacity-0 group-hover:opacity-100 focus:opacity-100",
            // Always visible on touch devices
            "sm:opacity-0 sm:group-hover:opacity-100",
            "@touch:opacity-100"
          )}
          aria-label="Remove product"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>

        {/* Product image */}
        <Link to={`/products/${product.id}`} className="block">
          <div className="relative h-64 w-full overflow-hidden bg-muted sm:h-72">
            {product.image_url ? (
              <>
                {/* Blurred background — same image scaled up to fill and softened */}
                <img
                  src={product.image_url}
                  aria-hidden
                  className="absolute inset-0 h-full w-full scale-125 object-cover blur-2xl opacity-50"
                />
                {/* Foreground image — fills full width, crops vertically if taller than container */}
                <img
                  src={product.image_url}
                  alt={product.title ?? "Product"}
                  className="relative h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
                  loading="lazy"
                />
              </>
            ) : (
              <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted to-muted/50">
                <ShoppingBag className="h-12 w-12 text-muted-foreground/40" />
              </div>
            )}
          </div>
        </Link>

        {/* Card body */}
        <div className="flex flex-1 flex-col gap-1.5 p-2.5">
          {/* Platform badge */}
          {product.platform && product.platform !== "generic" && (
            <Badge variant="secondary" className="w-fit text-[10px] capitalize">
              {product.platform}
            </Badge>
          )}

          {/* Title */}
          <Link
            to={`/products/${product.id}`}
            className="line-clamp-2 text-xs font-medium leading-snug hover:underline sm:text-sm"
          >
            {product.title ?? product.url}
          </Link>

          {/* Price */}
          <p className="text-sm font-bold tabular-nums sm:text-base">
            {formatPrice(product.current_price, product.currency)}
          </p>

          {/* Tags — hidden on very small screens to save space */}
          {product.tags.length > 0 && (
            <div className="hidden flex-wrap gap-1 sm:flex">
              {product.tags.map((tag) => (
                <Badge key={tag.id} variant="outline" className="text-[10px]">
                  {tag.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
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
