"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * The visitor's local hour, or null while rendering on the server. useSyncExternalStore lets React
 * render the server snapshot first and switch to the browser value during hydration without a mismatch.
 */
export function useClientHour(): number | null {
  return useSyncExternalStore(subscribe, () => new Date().getHours(), () => null);
}
