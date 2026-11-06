import { Compass } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Branded 404 inside the app shell: always offers a way back (DRD §13, no dead ends). */
export default function NotFound() {
  return (
    <div className="flex flex-col items-start gap-4 py-16 sm:items-center sm:text-center">
      <Compass aria-hidden="true" className="size-7 text-muted-foreground" />
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Page not found</h1>
        <p className="mt-1 max-w-prose text-muted-foreground">
          This page doesn&apos;t exist, or the feature hasn&apos;t been built yet.
        </p>
      </div>
      <Button asChild>
        <Link href="/">Back to overview</Link>
      </Button>
    </div>
  );
}
