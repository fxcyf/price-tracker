import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Save } from "lucide-react";
import { triggerPriceCheck, upsertWatchConfig, type WatchConfig } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface WatchConfigCardProps {
  productId: string;
  initial: WatchConfig | undefined;
}

export default function WatchConfigCard({ productId, initial }: WatchConfigCardProps) {
  const [isActive, setIsActive] = useState(true);
  const [dropPct, setDropPct] = useState(5);
  const [notifyOnRestock, setNotifyOnRestock] = useState(false);

  useEffect(() => {
    if (initial) {
      setIsActive(initial.is_active);
      setDropPct(initial.alert_on_drop_pct);
      setNotifyOnRestock(initial.notify_on_restock);
    }
  }, [initial]);

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const checkMutation = useMutation({
    mutationFn: () => triggerPriceCheck(productId),
    onSuccess: () => {
      toast({ title: "Price check queued — results will appear shortly" });
    },
    onError: () => {
      toast({ title: "Failed to queue price check", variant: "destructive" });
    },
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      upsertWatchConfig(productId, {
        is_active: isActive,
        alert_on_drop_pct: dropPct,
        notify_on_restock: notifyOnRestock,
      }).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["watch", productId], updated);
      toast({ title: "Monitoring settings saved" });
    },
    onError: () => {
      toast({ title: "Failed to save settings", variant: "destructive" });
    },
  });

  const lastChecked = initial?.last_checked_at
    ? new Date(initial.last_checked_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Never";

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <h2 className="text-sm font-semibold">Monitoring</h2>

      {/* Active toggle */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Track price</p>
          <p className="text-xs text-muted-foreground">Include this product in periodic checks</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={isActive}
          onClick={() => setIsActive((v) => !v)}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isActive ? "bg-primary" : "bg-input"
          )}
        >
          <span
            className={cn(
              "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition-transform",
              isActive ? "translate-x-5" : "translate-x-0"
            )}
          />
        </button>
      </div>

      {/* Drop alert threshold */}
      <div className="space-y-2">
        <Label htmlFor="drop-pct">Alert when price drops by (%)</Label>
        <div className="flex items-center gap-2">
          <Input
            id="drop-pct"
            type="number"
            min={0}
            max={100}
            value={dropPct}
            onChange={(e) => setDropPct(Number(e.target.value))}
            className="w-24"
          />
          <span className="text-sm text-muted-foreground">%</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Send an email alert when price falls by at least this percentage from the previous check.
          Set to 0 to alert on any drop.
        </p>
      </div>

      {/* Restock alert toggle */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Alert when back in stock</p>
          <p className="text-xs text-muted-foreground">Notify when an out-of-stock product becomes available</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={notifyOnRestock}
          onClick={() => setNotifyOnRestock((v) => !v)}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            notifyOnRestock ? "bg-primary" : "bg-input"
          )}
        >
          <span
            className={cn(
              "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition-transform",
              notifyOnRestock ? "translate-x-5" : "translate-x-0"
            )}
          />
        </button>
      </div>

      {/* Last checked + Check Now */}
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Last checked: <span className="font-medium text-foreground">{lastChecked}</span>
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => checkMutation.mutate()}
          disabled={checkMutation.isPending}
          className="h-7 shrink-0 text-xs"
        >
          {checkMutation.isPending ? (
            <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="mr-1.5 h-3 w-3" />
          )}
          Check Now
        </Button>
      </div>

      <Button
        size="sm"
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        className="w-full sm:w-auto"
      >
        {saveMutation.isPending ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Saving…
          </>
        ) : (
          <>
            <Save className="mr-2 h-4 w-4" />
            Save
          </>
        )}
      </Button>
    </div>
  );
}
