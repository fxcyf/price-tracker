# Mobile UX Patterns

## Clipboard Paste on iOS

`navigator.clipboard.readText()` called from a `useEffect` (i.e. on component mount / state change, not from a user interaction) is silently blocked by iOS Safari. It never throws — the promise just rejects or hangs.

**Pattern:** Keep the mount-time attempt as a best-effort for desktop/Android/Chrome, but always pair it with an **explicit paste button** in the UI. A direct `onClick` handler satisfies iOS's "user gesture" requirement.

```tsx
// Best-effort on open (desktop/Android)
useEffect(() => {
  if (!open) return;
  navigator.clipboard?.readText().then((text) => {
    if (text.trim().startsWith("http") && !url) setUrl(text.trim());
  }).catch(() => {});
}, [open]);

// Fallback paste button (iOS-safe)
{!url && navigator.clipboard && (
  <button type="button" onClick={() => {
    navigator.clipboard.readText().then((text) => {
      if (text.trim().startsWith("http")) setUrl(text.trim());
      else toast({ title: "Nothing URL-like in clipboard" });
    }).catch(() => toast({ title: "Could not read clipboard" }));
  }}>
    <Clipboard className="h-4 w-4" />
  </button>
)}
```

## Mobile Horizontal Overflow / Page Too Wide

Despite `<meta name="viewport" content="width=device-width, initial-scale=1.0" />`, any element wider than the viewport (including Radix UI portal dialogs rendered directly into `<body>`) can expand the document width, causing the mobile browser to zoom out the entire page.

**Fix:** Add `overflow-x: hidden` to both `html` and `body` in `index.css`. This is the safest global guard.

```css
@layer base {
  html {
    overflow-x: hidden;
  }
  body {
    @apply bg-background text-foreground;
    overflow-x: hidden;
  }
}
```

Note: Dialogs and other fixed/absolute portal elements rendered to `document.body` live **outside** the main `overflow-hidden` flex layout container, so they are not clipped by it.

## Inline Edit Pattern for a Single Field

When a single field (e.g. `image_url`) can be wrong and needs user correction, prefer an **inline edit** rather than a separate modal:

1. Show the current value with a hover-reveal edit button (pencil icon overlaid on the image).
2. On click, replace the display with an input + live preview + Save / Cancel buttons.
3. On save, call the mutation and update the query cache directly (`queryClient.setQueryData`) for instant feedback without a refetch.

This keeps the edit in context and avoids opening a new modal just to change one field.
