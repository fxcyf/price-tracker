import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShoppingBag, AlertCircle, Loader2 } from "lucide-react";
import { parseUrl, createProduct, type ParsePreview } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";

interface AddProductModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "Price not found";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);
}

type Step = "url" | "preview";

export default function AddProductModal({ open, onOpenChange }: AddProductModalProps) {
  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [preview, setPreview] = useState<ParsePreview | null>(null);

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const parseMutation = useMutation({
    mutationFn: (u: string) => parseUrl(u).then((r) => r.data),
    onSuccess: (data) => {
      setPreview(data);
      setStep("preview");
    },
  });

  const createMutation = useMutation({
    mutationFn: ({ u, tags }: { u: string; tags: string[] }) =>
      createProduct(u, tags).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast({ title: "Product added to tracker" });
      handleClose();
    },
    onError: () => {
      toast({ title: "Failed to add product", variant: "destructive" });
    },
  });

  function handleClose() {
    onOpenChange(false);
    // Reset after animation finishes
    setTimeout(() => {
      setStep("url");
      setUrl("");
      setTagsInput("");
      setPreview(null);
      parseMutation.reset();
      createMutation.reset();
    }, 200);
  }

  function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    parseMutation.mutate(trimmed);
  }

  function handleConfirm() {
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    createMutation.mutate({ u: url.trim(), tags });
  }

  const parseError = parseMutation.error as { response?: { status?: number } } | null;
  const parseErrorMessage =
    parseError?.response?.status === 422
      ? "Site is blocked or cookies have expired. Try importing cookies for this domain."
      : parseMutation.isError
      ? "Failed to fetch the URL. Please check it and try again."
      : null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="w-full max-w-lg mx-4">
        <DialogHeader>
          <DialogTitle>{step === "url" ? "Add Product" : "Confirm Product"}</DialogTitle>
        </DialogHeader>

        {step === "url" && (
          <form onSubmit={handlePreview} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="product-url">Product URL</Label>
              <Input
                id="product-url"
                type="url"
                placeholder="https://www.example.com/product"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                autoFocus
              />
            </div>

            {parseErrorMessage && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{parseErrorMessage}</span>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={parseMutation.isPending || !url.trim()}>
                {parseMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {parseMutation.isPending ? "Fetching…" : "Preview"}
              </Button>
            </div>
          </form>
        )}

        {step === "preview" && preview && (
          <div className="space-y-4">
            {/* Preview card */}
            <div className="flex gap-3 rounded-lg border bg-muted/40 p-3">
              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md bg-muted">
                {preview.image_url ? (
                  <img
                    src={preview.image_url}
                    alt={preview.title ?? "Product"}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <ShoppingBag className="h-6 w-6 text-muted-foreground/50" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="line-clamp-2 text-sm font-medium leading-snug">
                  {preview.title ?? url}
                </p>
                <p className="text-base font-bold tabular-nums">
                  {formatPrice(preview.price, preview.currency)}
                </p>
                <div className="flex flex-wrap gap-1">
                  {preview.platform && preview.platform !== "generic" && (
                    <Badge variant="secondary" className="text-xs capitalize">
                      {preview.platform}
                    </Badge>
                  )}
                  {preview.category && (
                    <Badge variant="outline" className="text-xs">
                      {preview.category}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {!preview.is_complete && (
              <div className="flex items-start gap-2 rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-700 dark:text-yellow-400">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Some details (e.g. price) could not be extracted. You can still add it and the tracker will retry later.</span>
              </div>
            )}

            {/* Tags */}
            <div className="space-y-2">
              <Label htmlFor="tags-input">Tags (optional)</Label>
              <Input
                id="tags-input"
                placeholder="shoes, sale, wishlist"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Comma-separated</p>
            </div>

            {createMutation.isError && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Failed to add product. Please try again.</span>
              </div>
            )}

            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => setStep("url")} disabled={createMutation.isPending}>
                Back
              </Button>
              <Button onClick={handleConfirm} disabled={createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {createMutation.isPending ? "Adding…" : "Add to tracker"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
