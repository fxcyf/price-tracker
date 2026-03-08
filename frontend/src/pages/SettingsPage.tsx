import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Info, Loader2, Save } from "lucide-react";
import { getSettings, updateSettings, type SettingsIn } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => getSettings().then((r) => r.data),
  });

  const [email, setEmail] = useState("");
  const [interval, setInterval] = useState(24);
  const [alertOnRise, setAlertOnRise] = useState(false);

  // Populate form once data loads
  useEffect(() => {
    if (settings) {
      setEmail(settings.notify_email ?? "");
      setInterval(settings.check_interval_hours);
      setAlertOnRise(settings.alert_on_rise);
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (data: SettingsIn) => updateSettings(data).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings"], updated);
      toast({ title: "Settings saved" });
    },
    onError: () => {
      toast({ title: "Failed to save settings", variant: "destructive" });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    saveMutation.mutate({
      notify_email: email || null,
      check_interval_hours: interval,
      alert_on_rise: alertOnRise,
    });
  }

  return (
    <div className="flex flex-col">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 flex h-14 items-center border-b bg-background px-4">
        <h1 className="text-base font-semibold">Settings</h1>
      </div>

      <div className="p-4">
        <div className="mx-auto w-full max-w-lg">
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                  <div className="h-9 rounded bg-muted animate-pulse" />
                </div>
              ))}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Notification email */}
              <div className="space-y-2">
                <Label htmlFor="notify-email">Notification email</Label>
                <Input
                  id="notify-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Price alerts will be sent to this address. Leave blank to disable email notifications.
                </p>
              </div>

              {/* Check interval */}
              <div className="space-y-2">
                <Label htmlFor="check-interval">Check interval (hours)</Label>
                <Input
                  id="check-interval"
                  type="number"
                  min={1}
                  max={168}
                  value={interval}
                  onChange={(e) => setInterval(Number(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  How often to check prices for all tracked products (1–168 hours).
                </p>
              </div>

              {/* Alert on rise toggle */}
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium">Alert on price rise</p>
                  <p className="text-xs text-muted-foreground">
                    Also send an alert when a price increases, not just when it drops.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={alertOnRise}
                  onClick={() => setAlertOnRise((v) => !v)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    alertOnRise ? "bg-primary" : "bg-input"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition-transform ${
                      alertOnRise ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {/* Info callout */}
              <div className="flex items-start gap-2 rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  Changing the check interval takes effect after restarting the Celery Beat worker.
                </span>
              </div>

              <Button type="submit" disabled={saveMutation.isPending} className="w-full sm:w-auto">
                {saveMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save settings
                  </>
                )}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
