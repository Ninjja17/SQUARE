"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/workflow", label: "Workflow" },
  { href: "/agents", label: "Agents" },
  { href: "/simulation", label: "Simulation" },
  { href: "/simulation/live", label: "Live View" },
  { href: "/report", label: "Report" },
];

export function NavBar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-[#1a1a1a] bg-black/90 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="text-white font-bold text-lg tracking-tight flex items-center gap-2">
          <span className="text-white">▣</span> SQUARE
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={clsx(
                "px-3 py-1.5 rounded-md text-sm transition-colors",
                pathname === link.href
                  ? "text-white bg-white/10 border border-white/20"
                  : "text-[#888] hover:text-white hover:bg-white/5"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
