import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/query-provider";
import { WorkspaceProvider } from "@/lib/workspace-context";
import { BrandProvider } from "@/components/brand/brand-context";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: {
    default: "Aentio · AI Content Optimizer",
    template: "%s · Aentio",
  },
  description:
    "Make any page clear, credible, and citable — for people, search engines, and AI answers. Grounded in your business knowledge graph.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full bg-background-canvas text-foreground font-sans">
        <QueryProvider>
          <WorkspaceProvider>
            <BrandProvider>
              <Shell>{children}</Shell>
            </BrandProvider>
          </WorkspaceProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
