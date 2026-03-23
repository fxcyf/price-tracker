import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingBag, AlertCircle, Clipboard, Cookie, Loader2, ChevronDown, ChevronUp, FlaskConical, Check } from "lucide-react";
import { parseUrl, createProduct, importCookies, getTags, addTestCase, type ParseDebug, type ParsePreview, type TestCaseIn } from "@/api/client";
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
  const [searchParams] = useSearchParams();
  const debugMode = searchParams.has("debug");

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
      .catch(() => { }); // permission denied or API unavailable — silent
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const parseMutation = useMutation({
    mutationFn: (u: string) => parseUrl(u).then((r) => r.data),
    onSuccess: (data) => {
      setPreview(data);
      setStep("preview");
    },
  });

  const createMutation = useMutation({
    mutationFn: ({ u, tags, saveAnyway = false }: { u: string; tags: string[]; saveAnyway?: boolean }) =>
      createProduct(u, tags, saveAnyway).then((r) => r.data),
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
    createMutation.mutate({ u: url.trim(), tags: selectedTags, saveAnyway: false });
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
                      onClick={() => createMutation.mutate({ u: url.trim(), tags: [], saveAnyway: true })}
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

            {/* Scrape trace — shown when ?debug is in the URL */}
            {debugMode && preview.debug && (
              <ScrapeDebugPanel debug={preview.debug} />
            )}

            {/* Add to test cases — debug only */}
            {debugMode && (
              <AddToTestCasePanel url={url} preview={preview} />
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

// ── Scrape debug panel (dev only) ─────────────────────────────────────────────

const SOURCE_STYLES: Record<string, { label: string; className: string }> = {
  opengraph: { label: "OpenGraph", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
  platform_rule: { label: "CSS rule", className: "bg-purple-500/15 text-purple-600 dark:text-purple-400" },
  learned_rule: { label: "Learned rule", className: "bg-orange-500/15 text-orange-600 dark:text-orange-400" },
  llm: { label: "LLM", className: "bg-pink-500/15 text-pink-600 dark:text-pink-400" },
  missing: { label: "missing", className: "bg-muted text-muted-foreground" },
};

const FIELD_LABELS: Record<string, string> = {
  title: "Title",
  price: "Price",
  image_url: "Image URL",
  brand: "Brand",
  category: "Category",
  platform: "Platform",
};

function ScrapeDebugPanel({ debug }: { debug: ParseDebug }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-dashed border-yellow-500/50 bg-yellow-500/5 p-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-xs font-semibold text-yellow-600 dark:text-yellow-400"
      >
        <span>
          DEV · Scrape Trace
          <span className="ml-2 font-normal text-yellow-500/70">
            {debug.layers_run.join(" → ")}
          </span>
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {open && (
        <div className="mt-2.5 space-y-1.5">
          {Object.entries(FIELD_LABELS).map(([key, label]) => {
            const field = debug.fields[key];
            if (!field) return null;
            const style = SOURCE_STYLES[field.source] ?? SOURCE_STYLES.missing;
            const displayValue =
              field.value === null || field.value === undefined
                ? <span className="text-muted-foreground/50">—</span>
                : <span className="truncate">{String(field.value)}</span>;

            return (
              <div key={key} className="grid grid-cols-[72px_80px_1fr] items-start gap-2 font-mono text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${style.className}`}>
                  {style.label}
                </span>
                <div className="min-w-0 space-y-0.5">
                  <div className="truncate text-foreground">{displayValue}</div>
                  {field.selector && (
                    <div className="truncate text-[10px] text-muted-foreground/70">
                      {field.selector}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Add to Test Cases panel (dev only) ──────────────────────────────────────

function autoLabel(url: string): string {
  try {
    const u = new URL(url);
    const domain = u.hostname.replace(/^www\./, "").split(".")[0];
    const parts = u.pathname.replace(/\/$/, "").split("/").filter(Boolean);
    const slug = parts[parts.length - 1] || "page";
    // Truncate slug to something readable
    const shortSlug = slug.length > 30 ? slug.slice(0, 30) : slug;
    return `${domain}/${shortSlug}`;
  } catch {
    return "";
  }
}

function deriveExpect(preview: ParsePreview): Record<string, string | null> {
  const expect: Record<string, string | null> = {};
  if (preview.price !== null) expect.price = "ok";
  if (preview.title !== null) expect.title = "ok";
  if (preview.image_url !== null) expect.image = "ok";
  // brand and in_stock: check debug fields if available
  const brand = preview.debug?.fields?.brand;
  if (brand && brand.value !== null && brand.value !== undefined) {
    expect.brand = "ok";
  }
  const inStock = preview.debug?.fields?.in_stock;
  if (inStock && inStock.value !== null && inStock.value !== undefined) {
    expect.in_stock = "ok";
  }
  return expect;
}

const EXPECT_FIELDS = ["price", "title", "image", "brand", "in_stock"] as const;
function AddToTestCasePanel({ url, preview }: { url: string; preview: ParsePreview }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(() => autoLabel(url));
  const [note, setNote] = useState("");
  const [expect, setExpect] = useState<Record<string, string | null>>(() => deriveExpect(preview));

  const mutation = useMutation({
    mutationFn: (data: TestCaseIn) => addTestCase(data),
    onSuccess: () => {
      toast({ title: "Added to test cases" });
      setOpen(false);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? "Failed to add test case";
      toast({ title: detail, variant: "destructive" });
    },
  });

  function handleSubmit() {
    const expectPayload: Record<string, string | null> = {};
    for (const f of EXPECT_FIELDS) {
      expectPayload[f] = expect[f] === "skip" ? null : (expect[f] ?? null);
    }
    mutation.mutate({
      url: url.trim(),
      label,
      fetch: "ok",
      expect: expectPayload,
      note,
    });
  }

  function cycleExpect(field: string) {
    setExpect((prev) => {
      const current = prev[field];
      // cycle: ok → none → skip → ok
      const next = current === "ok" ? "none" : current === "none" ? "skip" : "ok";
      return { ...prev, [field]: next };
    });
  }

  return (
    <div className="rounded-lg border border-dashed border-green-500/50 bg-green-500/5 p-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-xs font-semibold text-green-600 dark:text-green-400"
      >
        <span className="flex items-center gap-1.5">
          <FlaskConical className="h-3.5 w-3.5" />
          DEV · Add to Test Cases
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {/* Label */}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Label</label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="domain/slug"
              className="h-7 text-xs"
            />
          </div>

          {/* Expected fields */}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Expected fields (click to cycle)</label>
            <div className="flex flex-wrap gap-1.5">
              {EXPECT_FIELDS.map((field) => {
                const val = expect[field] ?? "skip";
                const colors: Record<string, string> = {
                  ok: "bg-green-500/15 text-green-600 dark:text-green-400 border-green-500/30",
                  none: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30",
                  skip: "bg-muted text-muted-foreground border-muted",
                };
                return (
                  <button
                    key={field}
                    type="button"
                    onClick={() => cycleExpect(field)}
                    className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-medium transition-colors ${colors[val]}`}
                  >
                    {field.replace("_", " ")}
                    <span className="opacity-60">= {val}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Note */}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Note</label>
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Description of this test case"
              className="h-7 text-xs"
            />
          </div>

          {/* Submit */}
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={mutation.isPending || mutation.isSuccess}
            className="w-full text-xs"
          >
            {mutation.isPending ? (
              <><Loader2 className="mr-1.5 h-3 w-3 animate-spin" />Adding…</>
            ) : mutation.isSuccess ? (
              <><Check className="mr-1.5 h-3 w-3" />Added</>
            ) : (
              <><FlaskConical className="mr-1.5 h-3 w-3" />Add to cases.json</>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
