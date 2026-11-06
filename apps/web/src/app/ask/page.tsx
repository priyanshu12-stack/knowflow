import type { Metadata } from "next";

import { AskView } from "@/components/ask/ask-view";

export const metadata: Metadata = { title: "Ask KnowFlow" };

/** DRD §7.3 Ask KnowFlow. */
export default function AskPage() {
  return <AskView />;
}
