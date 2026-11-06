"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * The viewer's local date. The server snapshot is empty so the prerendered shell never bakes in
 * the build date, and hydration doesn't mismatch.
 */
export function CurrentDate() {
  const label = useSyncExternalStore(subscribe, todayLabel, () => null);
  return <span className="tabular-nums">{label ?? " "}</span>;
}
