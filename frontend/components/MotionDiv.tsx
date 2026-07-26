"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

interface MotionDivProps {
  children: ReactNode;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
  blur?: boolean;
  className?: string;
  duration?: number;
}

const directionOffset = {
  up: { y: 24 },
  down: { y: -24 },
  left: { x: 24 },
  right: { x: -24 },
};

export function MotionDiv({
  children,
  delay = 0,
  direction = "up",
  blur = true,
  className = "",
  duration = 0.5,
}: MotionDivProps) {
  const offset = directionOffset[direction];

  return (
    <motion.div
      initial={{
        opacity: 0,
        ...offset,
        ...(blur ? { filter: "blur(8px)" } : {}),
      }}
      animate={{
        opacity: 1,
        x: 0,
        y: 0,
        filter: "blur(0px)",
      }}
      transition={{
        duration,
        delay,
        ease: [0.25, 0.4, 0.25, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
