"use client";

import { useEffect, useState } from "react";

interface PixelGridProps {
  columns?: number;
  rows?: number;
  flashCount?: number;
  interval?: number;
  opacity?: number;
}

export function PixelGrid({
  columns = 40,
  rows = 25,
  flashCount = 5,
  interval = 200,
  opacity = 0.5,
}: PixelGridProps) {
  const [flashingDots, setFlashingDots] = useState<Set<number>>(new Set());
  const totalDots = columns * rows;

  useEffect(() => {
    const timer = setInterval(() => {
      const newFlashing = new Set<number>();
      for (let i = 0; i < flashCount; i++) {
        newFlashing.add(Math.floor(Math.random() * totalDots));
      }
      setFlashingDots(newFlashing);
    }, interval);

    return () => clearInterval(timer);
  }, [totalDots, flashCount, interval]);

  return (
    <div
      className="fixed inset-0 pointer-events-none -z-20 overflow-hidden"
      style={{ opacity }}
    >
      <div
        className="w-full h-full grid"
        style={{
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
          gap: "0px",
        }}
      >
        {Array.from({ length: totalDots }, (_, i) => {
          const isFlashing = flashingDots.has(i);
          return (
            <div
              key={i}
              className="flex items-center justify-center"
            >
              <div
                className="rounded-full transition-all duration-400"
                style={{
                  width: "2px",
                  height: "2px",
                  backgroundColor: isFlashing
                    ? "rgba(255,255,255,0.9)"
                    : "rgba(255,255,255,0.05)",
                  boxShadow: isFlashing
                    ? "0 0 6px rgba(255,255,255,0.8), 0 0 12px rgba(100,200,255,0.5)"
                    : "none",
                  transform: isFlashing ? "scale(2)" : "scale(1)",
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
