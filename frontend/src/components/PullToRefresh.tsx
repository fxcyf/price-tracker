import { useCallback, useRef, useState, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";

const THRESHOLD = 60;
const MAX_PULL = 80;

interface PullToRefreshProps {
  onRefresh: () => Promise<unknown>;
  children: ReactNode;
}

export default function PullToRefresh({ onRefresh, children }: PullToRefreshProps) {
  const [pulling, setPulling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const startY = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (refreshing) return;
      const scrollTop = containerRef.current?.closest("main")?.scrollTop ?? 0;
      if (scrollTop > 0) return;
      startY.current = e.touches[0].clientY;
      setPulling(true);
    },
    [refreshing],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!pulling || refreshing) return;
      const delta = e.touches[0].clientY - startY.current;
      if (delta < 0) {
        setPullDistance(0);
        return;
      }
      setPullDistance(Math.min(delta * 0.4, MAX_PULL));
    },
    [pulling, refreshing],
  );

  const handleTouchEnd = useCallback(async () => {
    if (!pulling || refreshing) return;
    setPulling(false);

    if (pullDistance >= THRESHOLD) {
      setRefreshing(true);
      setPullDistance(40);
      try {
        await onRefresh();
      } finally {
        setRefreshing(false);
        setPullDistance(0);
      }
    } else {
      setPullDistance(0);
    }
  }, [pulling, refreshing, pullDistance, onRefresh]);

  const progress = Math.min(pullDistance / THRESHOLD, 1);

  return (
    <div
      ref={containerRef}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Pull indicator */}
      <div
        className="flex items-center justify-center overflow-hidden"
        style={{
          height: pullDistance > 0 ? `${pullDistance}px` : 0,
          transition: pulling ? "none" : "height 0.2s ease-out",
        }}
      >
        <RefreshCw
          className={`h-4 w-4 text-muted-foreground ${refreshing ? "animate-spin" : ""}`}
          style={{
            transform: refreshing ? undefined : `rotate(${progress * 360}deg)`,
            opacity: progress,
          }}
        />
      </div>
      {children}
    </div>
  );
}
