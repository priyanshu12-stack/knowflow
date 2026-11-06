import type { Metadata } from "next";

import { LibraryView } from "@/components/library/library-view";

export const metadata: Metadata = { title: "Knowledge Library" };

/** DRD §7.2 Knowledge Library: upload, list and manage workspace documents. */
export default function LibraryPage() {
  return <LibraryView />;
}
