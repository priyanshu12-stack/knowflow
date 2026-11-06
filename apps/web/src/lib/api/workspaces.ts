import { requestJson } from "./client";
import { bool, obj, str } from "./validate";

export interface Workspace {
  id: string;
  name: string;
  isDefault: boolean;
}

export const WORKSPACE_NAME_MAX = 80;

export function parseWorkspace(raw: unknown): Workspace {
  const o = obj(raw, "workspace");
  return {
    id: str(o, "id", "workspace"),
    name: str(o, "name", "workspace"),
    isDefault: bool(o, "is_default", "workspace"),
  };
}

export async function fetchCurrentWorkspace(signal?: AbortSignal) {
  return (await requestJson("/api/v1/workspaces/current", parseWorkspace, { signal })).data;
}

export async function renameWorkspace(id: string, name: string) {
  const res = await requestJson(`/api/v1/workspaces/${encodeURIComponent(id)}`, parseWorkspace, {
    method: "PATCH",
    json: { name },
  });
  return res.data;
}
