"use client";

import { useEffect, useState } from "react";

import { fetchCurrentWorkspace } from "@/lib/api/workspaces";

/** The workspace's real name under the wordmark (DRD §6.1); a neutral label until it loads. */
export function WorkspaceName() {
  const [name, setName] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    const refresh = () =>
      fetchCurrentWorkspace(ctrl.signal).then(
        (w) => setName(w.name),
        () => undefined,
      );
    void refresh();
    // The Overview's rename dialog announces changes so the sidebar stays in sync.
    window.addEventListener("knowflow:workspace-renamed", refresh);
    return () => {
      ctrl.abort();
      window.removeEventListener("knowflow:workspace-renamed", refresh);
    };
  }, []);
  return (
    <p className="truncate pl-8 text-[12px] text-muted-foreground" title={name ?? undefined}>
      {name ?? "Local workspace"}
    </p>
  );
}
