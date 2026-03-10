import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingBag, AlertCircle, Clipboard, Cookie, Loader2 } from "lucide-react";
import { parseUrl, createProduct, importCookies, getTags, type ParsePreview } from "@/api/client";
import { TagInput } from "@/components/TagInput";
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
import { cn } from "@/lib/utils";  // used in curl textarea

interface AddProductModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "Price not found";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);
}

type Step = "url" | "cookies" | "preview";

function parseDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// ── Main modal ────────────────────────────────────────────────────────────────

export default function AddProductModal({ open, onOpenChange }: AddProductModalProps) {
  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const [curlInput, setCurlInput] = useState("");

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: allTags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: () => getTags().then((r) => r.data),
  });

  // On open, try to pre-fill from clipboard if it contains a URL
  useEffect(() => {
    if (!open) return;
    navigator.clipboard?.readText()
      .then((text) => {
        const trimmed = text.trim();
        if (trimmed.startsWith("http") && !url) {
          setUrl(trimmed);
        }
      })
      .catch(() => {}); // permission denied or API unavailable — silent
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

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
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast({ title: "Product added to tracker" });
      handleClose();
    },
    onError: () => {
      toast({ title: "Failed to add product", variant: "destructive" });
    },
  });

  const cookieMutation = useMutation({
    mutationFn: (domain: string) => importCookies(domain, curlInput),
    onSuccess: (res) => {
      const domain = parseDomain(url);
      queryClient.setQueryData(["cookies", domain], res.data);
      toast({ title: `Cookies imported — retrying preview…` });
      setCurlInput("");
      parseMutation.mutate(url.trim());
      setStep("url");
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? "Failed to import cookies";
      toast({ title: detail, variant: "destructive" });
    },
  });

  function handleClose() {
    onOpenChange(false);
    setTimeout(() => {
      setStep("url");
      setUrl("");
      setSelectedTags([]);
      setPreview(null);
      setCurlInput("");
      parseMutation.reset();
      createMutation.reset();
      cookieMutation.reset();
    }, 200);
  }

  function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    parseMutation.mutate(trimmed);
  }

  function handleConfirm() {
    createMutation.mutate({ u: url.trim(), tags: selectedTags });
  }

  const parseError = parseMutation.error as { response?: { status?: number } } | null;
  const isBlocked = parseError?.response?.status === 422;
  const parseErrorMessage = isBlocked
    ? "Site is blocked or cookies have expired."
    : parseMutation.isError
    ? "Failed to fetch the URL. Please check it and try again."
    : null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="w-full max-w-lg mx-4">
        <DialogHeader>
          <DialogTitle>
            {step === "url" ? "Add Product" : step === "cookies" ? "Import Cookies" : "Confirm Product"}
          </DialogTitle>
        </DialogHeader>

        {/* ── Step: URL ── */}
        {step === "url" && (
          <form onSubmit={handlePreview} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="product-url">Product URL</Label>
              <div className="relative">
                <Input
                  id="product-url"
                  type="url"
                  placeholder="https://www.example.com/product"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  autoFocus
                  className={!url && navigator.clipboard ? "pr-9" : ""}
                />
                {!url && navigator.clipboard && (
                  <button
                    type="button"
                    aria-label="Paste URL from clipboard"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => {
                      navigator.clipboard.readText()
                        .then((text) => {
                          const trimmed = text.trim();
                          if (trimmed.startsWith("http")) {
                            setUrl(trimmed);
                          } else {
                            toast({ title: "Nothing URL-like in clipboard" });
                          }
                        })
                        .catch(() => toast({ title: "Could not read clipboard" }));
                    }}
                  >
                    <Clipboard className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>

            {parseErrorMessage && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive space-y-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{parseErrorMessage}</span>
                </div>
                {isBlocked && (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setStep("cookies")}
                    >
                      <Cookie className="mr-2 h-3.5 w-3.5" />
                      Import Cookies for {parseDomain(url)}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                      disabled={createMutation.isPending}
                      onClick={() => createMutation.mutate({ u: url.trim(), tags: [] })}
                    >
                      {createMutation.isPending
                        ? <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />Saving…</>
                        : "Save URL anyway"
                      }
                    </Button>
                  </div>
                )}
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

        {/* ── Step: Cookie import ── */}
        {step === "cookies" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Cookie className="h-4 w-4" />
              <span>Importing cookies for <span className="font-medium text-foreground">{parseDomain(url)}</span></span>
            </div>

            <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
              <p className="font-medium text-foreground">How to copy a cURL command:</p>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>Open the product page in your browser</li>
                <li>Open DevTools → Network tab</li>
                <li>Reload the page, right-click any request to the site</li>
                <li>Select <span className="font-medium text-foreground">Copy → Copy as cURL</span></li>
                <li>Paste below</li>
              </ol>
            </div>

            <div className="space-y-2">
              <Label htmlFor="curl-input">cURL command</Label>
              <textarea
                id="curl-input"
                value={curlInput}
                onChange={(e) => setCurlInput(e.target.value)}
                placeholder={"curl 'https://example.com/product' \\\n  -H 'cookie: session=...; _px3=...'"}
                rows={5}
                className={cn(
                  "w-full rounded-md border bg-background px-3 py-2 text-xs font-mono",
                  "placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                )}
              />
            </div>

            {cookieMutation.isError && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{(cookieMutation.error as any)?.response?.data?.detail ?? "Failed to import cookies"}</span>
              </div>
            )}

            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => setStep("url")} disabled={cookieMutation.isPending}>
                Back
              </Button>
              <Button
                onClick={() => cookieMutation.mutate(parseDomain(url))}
                disabled={cookieMutation.isPending || !curlInput.trim()}
              >
                {cookieMutation.isPending ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Importing…</>
                ) : (
                  "Import & Retry"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* ── Step: Preview & confirm ── */}
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
              <Label>Tags (optional)</Label>
              <TagInput
                selected={selectedTags}
                onChange={setSelectedTags}
                suggestions={allTags}
              />
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
