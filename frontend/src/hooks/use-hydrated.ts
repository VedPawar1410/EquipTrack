"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False on the server and during hydration, true afterwards. Parts of the shell that show fetched data
 * (who is signed in, notification counts) hydrate inside Suspense boundaries that can resume *after*
 * that data has already arrived in the browser; rendering it then would differ from the server HTML.
 * Gating on this keeps the first client render identical to the server's.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}
