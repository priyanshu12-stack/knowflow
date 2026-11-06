/**
 * Tiny runtime validators for API payloads. A failure throws TypeError, which the client turns
 * into an `invalid_response` ApiError. Kept dependency-free on purpose.
 */

export type Obj = Record<string, unknown>;

export function fail(path: string): never {
  throw new TypeError(`invalid payload at ${path}`);
}

export function obj(raw: unknown, path: string): Obj {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) fail(path);
  return raw as Obj;
}

export function str(o: Obj, key: string, path: string): string {
  const v = o[key];
  if (typeof v !== "string") fail(`${path}.${key}`);
  return v;
}

export function int(o: Obj, key: string, path: string): number {
  const v = o[key];
  if (typeof v !== "number" || !Number.isInteger(v)) fail(`${path}.${key}`);
  return v;
}

export function bool(o: Obj, key: string, path: string): boolean {
  const v = o[key];
  if (typeof v !== "boolean") fail(`${path}.${key}`);
  return v;
}

export function nullableStr(o: Obj, key: string, path: string): string | null {
  return o[key] === null || o[key] === undefined ? null : str(o, key, path);
}

export function nullableInt(o: Obj, key: string, path: string): number | null {
  return o[key] === null || o[key] === undefined ? null : int(o, key, path);
}

export function oneOf<T extends string>(
  o: Obj,
  key: string,
  values: readonly T[],
  path: string,
): T {
  const v = o[key];
  if (!values.includes(v as T)) fail(`${path}.${key}`);
  return v as T;
}

export function arr<T>(o: Obj, key: string, path: string, item: (raw: unknown, p: string) => T) {
  const v = o[key];
  if (!Array.isArray(v)) fail(`${path}.${key}`);
  return v.map((x, i) => item(x, `${path}.${key}[${i}]`));
}
