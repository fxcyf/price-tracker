import { useState, useEffect, useRef } from "react";
import { Loader2, Plus, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagInputProps {
  selected: string[];
  onChange: (tags: string[]) => void;
  suggestions?: string[];
  /** Show a subtle saving indicator while a mutation is in flight */
  saving?: boolean;
  /** Called when the user clicks "Suggest" — should return candidate tags */
  onSuggest?: () => Promise<string[]>;
}

export function TagInput({ selected, onChange, suggestions = [], saving = false, onSuggest }: TagInputProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  // Pending suggestions shown below the input for user review
  const [pending, setPending] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = suggestions.filter(
    (s) =>
      s.toLowerCase().includes(query.toLowerCase()) &&
      !selected.includes(s)
  );
  const canAddNew =
    query.trim() !== "" &&
    !selected.includes(query.trim()) &&
    !suggestions.includes(query.trim());

  function addTag(tag: string) {
    const t = tag.trim().toLowerCase();
    if (t && !selected.includes(t)) {
      onChange([...selected, t]);
    }
    // If this tag was pending, remove it from pending
    setPending((prev) => prev.filter((p) => p !== t));
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  }

  function removeTag(tag: string) {
    onChange(selected.filter((t) => t !== tag));
  }

  function acceptPending(tag: string) {
    if (!selected.includes(tag)) {
      onChange([...selected, tag]);
    }
    setPending((prev) => prev.filter((p) => p !== tag));
  }

  function dismissPending(tag: string) {
    setPending((prev) => prev.filter((p) => p !== tag));
  }

  function acceptAllPending() {
    const toAdd = pending.filter((t) => !selected.includes(t));
    if (toAdd.length > 0) onChange([...selected, ...toAdd]);
    setPending([]);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if ((e.key === "Enter" || e.key === ",") && query.trim()) {
      e.preventDefault();
      addTag(query);
    } else if (e.key === "Backspace" && !query && selected.length > 0) {
      onChange(selected.slice(0, -1));
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function handleSuggest() {
    if (!onSuggest || suggesting) return;
    setSuggesting(true);
    setPending([]);
    try {
      const newTags = await onSuggest();
      // Show as pending proposals — exclude already selected
      const proposals = newTags.filter((t) => !selected.includes(t));
      setPending(proposals);
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <div ref={containerRef} className="relative space-y-2">
      {/* Main chip + input row */}
      <div
        className={cn(
          "flex min-h-9 flex-wrap gap-1.5 rounded-md border bg-background px-3 py-2 text-sm",
          "focus-within:ring-2 focus-within:ring-ring cursor-text",
          saving && "opacity-60"
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {selected.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
          >
            {tag}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              className="text-primary/60 hover:text-primary"
              aria-label={`Remove ${tag}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          disabled={saving}
          placeholder={selected.length === 0 ? "Add tags…" : ""}
          className="min-w-[80px] flex-1 bg-transparent outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        />
        {saving && (
          <span className="self-center text-xs text-muted-foreground">Saving…</span>
        )}
      </div>

      {/* Dropdown */}
      {open && !saving && (filtered.length > 0 || canAddNew) && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          <ul className="max-h-40 overflow-y-auto py-1 text-sm">
            {filtered.map((tag) => (
              <li key={tag}>
                <button
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); addTag(tag); }}
                  className="w-full px-3 py-1.5 text-left capitalize hover:bg-accent hover:text-accent-foreground"
                >
                  {tag}
                </button>
              </li>
            ))}
            {canAddNew && (
              <li>
                <button
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); addTag(query); }}
                  className="w-full px-3 py-1.5 text-left text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                >
                  Add "<span className="font-medium text-foreground">{query.trim()}</span>"
                </button>
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Pending suggestions row */}
      {pending.length > 0 && (
        <div className="rounded-md border border-dashed bg-muted/30 px-3 py-2 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              Suggestions — click to add
            </p>
            <button
              type="button"
              onClick={acceptAllPending}
              className="text-xs text-primary hover:underline"
            >
              Add all
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {pending.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-md border border-dashed px-2 py-0.5 text-xs text-muted-foreground"
              >
                <button
                  type="button"
                  onClick={() => acceptPending(tag)}
                  className="hover:text-foreground flex items-center gap-1"
                  aria-label={`Add ${tag}`}
                >
                  <Plus className="h-2.5 w-2.5" />
                  {tag}
                </button>
                <button
                  type="button"
                  onClick={() => dismissPending(tag)}
                  className="text-muted-foreground/50 hover:text-muted-foreground"
                  aria-label={`Dismiss ${tag}`}
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer row */}
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Select from existing tags or type a new one and press Enter
        </p>
        {onSuggest && (
          <button
            type="button"
            onClick={handleSuggest}
            disabled={suggesting || saving}
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium",
              "text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors",
              "disabled:cursor-not-allowed disabled:opacity-50"
            )}
          >
            {suggesting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3" />
            )}
            {suggesting ? "Suggesting…" : "Suggest"}
          </button>
        )}
      </div>
    </div>
  );
}
