"use client";

import { useEffect, useState } from "react";

interface TypingTextProps {
  text: string;
  speed?: number;
  className?: string;
  cursor?: boolean;
}

export function TypingText({ text, speed = 40, className = "", cursor = true }: TypingTextProps) {
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    setDisplayed("");
    let i = 0;
    const timer = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(timer);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed]);

  return (
    <span className={className}>
      {displayed}
      {cursor && <span className="inline-block w-[2px] h-[1em] bg-white ml-0.5 align-middle animate-[typing-cursor_0.8s_infinite]" />}
    </span>
  );
}
