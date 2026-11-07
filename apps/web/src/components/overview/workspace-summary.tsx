"use client";

import { Files, Pencil } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { fetchDocuments } from "@/lib/api/documents";
import {
  fetchCurrentWorkspace,
  renameWorkspace,
  WORKSPACE_NAME_MAX,
  type Workspace,
} from "@/lib/api/workspaces";

type SummaryState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; workspace: Workspace; documents: number; ready: number };

function RenameDialog({
  workspace,
  open,
  onOpenChange,
  onRenamed,
}: {
  workspace: Workspace;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRenamed: (ws: Workspace) => void;
}) {
  const inputId = useId();
  const errorId = useId();
  const [name, setName] = useState(workspace.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = name.trim();
  const invalid = trimmed.length === 0 || trimmed.length > WORKSPACE_NAME_MAX;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (invalid) {
      setError(`Enter a name between 1 and ${WORKSPACE_NAME_MAX} characters.`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await renameWorkspace(workspace.id, trimmed);
      onRenamed(updated);
      window.dispatchEvent(new Event("knowflow:workspace-renamed"));
      onOpenChange(false);
      toast.success(`Workspace renamed to “${updated.name}”.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The workspace could not be renamed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (saving) return;
        if (next) {
          setName(workspace.name);
          setError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Rename workspace</DialogTitle>
            <DialogDescription>
              The name is shown across KnowFlow. Documents and settings are not affected.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor={inputId}>Workspace name</Label>
            <Input
              id={inputId}
              value={name}
              maxLength={WORKSPACE_NAME_MAX}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
              autoComplete="off"
            />
            {error && (
              <p id={errorId} role="alert" className="text-[13px]">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save name"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** DRD §7.1: workspace name, real document counts and a quick action into the Library. */
export function WorkspaceSummary() {
  const [state, setState] = useState<SummaryState>({ kind: "loading" });
  const [renaming, setRenaming] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      fetchCurrentWorkspace(ctrl.signal),
      fetchDocuments({ limit: 1, offset: 0 }, ctrl.signal),
      fetchDocuments({ limit: 1, offset: 0, status: "ready" }, ctrl.signal),
    ]).then(
      ([workspace, all, ready]) =>
        setState({ kind: "loaded", workspace, documents: all.total, ready: ready.total }),
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof ApiError ? err.message : "Workspace details could not be loaded.",
        });
      },
    );
    return () => ctrl.abort();
  }, []);

  return (
    <section aria-labelledby="workspace-heading" className="rounded-xl border bg-card px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
            Workspace
          </p>
          {state.kind === "loading" && <Skeleton className="mt-1.5 h-6 w-44" />}
          {state.kind === "loaded" && (
            <div className="mt-0.5 flex items-center gap-1">
              <h2 id="workspace-heading" className="truncate text-[18px] font-semibold">
                {state.workspace.name}
              </h2>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setRenaming(true)}
                aria-label="Rename workspace"
              >
                <Pencil aria-hidden="true" />
              </Button>
            </div>
          )}
          {state.kind === "error" && (
            <>
              <h2 id="workspace-heading" className="mt-0.5 text-[18px] font-semibold">
                Workspace unavailable
              </h2>
              <p className="mt-0.5 text-muted-foreground">
                {state.message} See System readiness below.
              </p>
            </>
          )}
          {state.kind === "loaded" && (
            <p className="mt-0.5 text-muted-foreground tabular-nums">
              {state.documents === 0
                ? "No documents yet."
                : `${state.documents} document${state.documents === 1 ? "" : "s"} · ${state.ready} indexed`}
            </p>
          )}
        </div>
        <Button
          asChild
          variant={state.kind === "loaded" && state.documents === 0 ? "default" : "outline"}
        >
          <Link href="/library">
            <Files aria-hidden="true" />
            {state.kind === "loaded" && state.documents === 0
              ? "Upload documents"
              : "Open Knowledge Library"}
          </Link>
        </Button>
      </div>
      {state.kind === "loaded" && (
        <RenameDialog
          workspace={state.workspace}
          open={renaming}
          onOpenChange={setRenaming}
          onRenamed={(workspace) =>
            setState((s) => (s.kind === "loaded" ? { ...s, workspace } : s))
          }
        />
      )}
    </section>
  );
}
