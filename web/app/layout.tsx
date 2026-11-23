import type { Metadata } from "next";
import { Playfair_Display, Plus_Jakarta_Sans } from "next/font/google";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const display = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display-next",
  weight: ["500", "600"],
});

const ui = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-ui-next",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Bangalore Bites",
  description:
    "AI-powered Bangalore restaurant recommendations with rankings and explanations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${display.variable} ${ui.variable}`}>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0"
          rel="stylesheet"
        />
      </head>
      <body
        style={
          {
            "--font-display": "var(--font-display-next), Georgia, serif",
            "--font-ui": "var(--font-ui-next), 'Segoe UI', sans-serif",
          } as React.CSSProperties
        }
      >
        <div className="hero-wash" aria-hidden />
        <SiteHeader />
        <main className="app-shell">{children}</main>
      </body>
    </html>
  );
}
