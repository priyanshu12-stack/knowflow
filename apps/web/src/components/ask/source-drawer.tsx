"use client";

import { ExternalLink, Quote } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { citationLocation, type Citation } from "@/lib/api/chat";

/** DRD §7.3 / §8 source drawer: document, page/section, the exact excerpt, open action. */
export function SourceDrawer({
  citation,
  onClose,
}: {
  citation: Citation | null;
  onClose: () => void;
}) {
  return (
    <Sheet open={citation !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {citation && (
          <>
            <SheetHeader className="border-b px-6 py-5">
              <p className="font-mono text-[12px] text-muted-foreground">
                Source [{citation.number}]
              </p>
              <SheetTitle className="pr-8 text-[18px] font-semibold break-words">
                {citation.documentName}
              </SheetTitle>
              <SheetDescription>
                {citationLocation(citation) ?? "Whole document (no page or heading information)"}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-4 px-6 pb-8">
              <figure className="rounded-lg border bg-background p-4">
                <Quote aria-hidden="true" className="size-4 text-muted-foreground" />
                <blockquote className="mt-2 text-[14px] leading-[1.65] whitespace-pre-wrap">
                  {citation.excerpt}
                </blockquote>
                <figcaption className="mt-3 text-[12px] text-muted-foreground">
                  The exact passage the answer was generated from.
                </figcaption>
              </figure>
              <Button asChild variant="outline" className="self-start">
                <Link href={`/library?document=${encodeURIComponent(citation.documentId)}`}>
                  <ExternalLink aria-hidden="true" />
                  Open document in Library
                </Link>
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
