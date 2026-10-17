"use client";

import { useEffect } from "react";

/**
 * Sets the document title for client-rendered pages. The root layout keeps the
 * default title for the first paint; this refines it once the view mounts.
 */
export function usePageTitle(title: string): void {
  useEffect(() => {
    const previous = document.title;
    document.title = `${title} · EntityGraph Auditor`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
