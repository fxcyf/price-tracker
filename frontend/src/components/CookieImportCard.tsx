import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Cookie, Loader2 } from "lucide-react";
import { getCookieStatus, importCookies, type Product } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface CookieImportCardProps {
  product: Product;
}

function parseDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function StatusBadge({ status }: { status: string }) {
  if (status === "valid") {
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Valid</Badge>;
  }
  if (status === "expired") {
    return <Badge className="bg-red-100 text-red-800 hover:bg-red-100">Expired</Badge>;
  }
  return <Badge variant="secondary">None</Badge>;
}

export default function CookieImportCard({ product }: CookieImportCardProps) {
  const domain = parseDomain(product.url);
  const [expanded, setExpanded] = useState(false);
  const [curl, setCurl] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: cookieStatus } = useQuery({
    queryKey: ["cookies", domain],
    queryFn: () => getCookieStatus(domain).then((r) => r.data),
  });

  const importMutation = useMutation({
    mutationFn: () => importCookies(domain, curl),
    onSuccess: (res) => {
      queryClient.setQueryData(["cookies", domain], res.data);
      toast({ title: `Cookies imported — ${res.data.cookie_count ?? 0} cookies saved for ${domain}` });
      setCurl("");
      setExpanded(false);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? "Failed to import cookies";
      toast({ title: detail, variant: "destructive" });
    },
  });

  const updatedAt = cookieStatus?.updated_at
    ? new Date(cookieStatus.updated_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Cookie className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold">Cookie Import</h2>
          <span className="text-xs text-muted-foreground font-mono">{domain}</span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          aria-expanded={expanded}
        >
          {expanded ? (
            <><ChevronUp className="h-3.5 w-3.5" /> Hide</>
          ) : (
            <><ChevronDown className="h-3.5 w-3.5" /> Import</>
          )}
        </button>
      </div>

      {/* Status row */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <StatusBadge status={cookieStatus?.status ?? "none"} />
        {cookieStatus?.cookie_count != null && (
          <span>{cookieStatus.cookie_count} cookie{cookieStatus.cookie_count !== 1 ? "s" : ""}</span>
        )}
        {updatedAt && <span>· updated {updatedAt}</span>}
      </div>

      {/* Collapsible import form */}
      {expanded && (
        <div className="space-y-3 pt-1">
          <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">How to get a cURL command:</p>
            <ol className="list-decimal list-inside space-y-0.5">
              <li>Open the product page in your browser and log in if needed</li>
              <li>Open DevTools → Network tab</li>
              <li>Reload the page, then right-click any request to the site</li>
              <li>Select <span className="font-medium text-foreground">Copy → Copy as cURL</span></li>
              <li>Paste the result below</li>
            </ol>
          </div>

          <textarea
            value={curl}
            onChange={(e) => setCurl(e.target.value)}
            placeholder={'curl \'https://example.com/product\' \\\n  -H \'cookie: session=...; _px3=...\''}
            rows={5}
            className={cn(
              "w-full rounded-md border bg-background px-3 py-2 text-xs font-mono",
              "placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring",
              "resize-y"
            )}
          />

          <Button
            size="sm"
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending || !curl.trim()}
            className="w-full sm:w-auto"
          >
            {importMutation.isPending ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Importing…</>
            ) : (
              "Import Cookies"
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
