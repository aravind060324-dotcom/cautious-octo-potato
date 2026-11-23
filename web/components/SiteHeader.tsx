"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Search" },
  { href: "/favorites", label: "Favorites" },
  { href: "/compare", label: "Compare" },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="app-header">
      <h1 className="brand">Bangalore Bites</h1>
      <p className="tagline">
        Tell us what you want. We’ll rank real restaurants and explain why.
      </p>
      <nav className="app-nav" aria-label="Primary">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href ? "is-active" : undefined}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
