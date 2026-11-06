import type { Metadata } from "next";

import { SqlView } from "@/components/sql/sql-view";

export const metadata: Metadata = { title: "SQL Analyst" };

/** DRD §7.4 SQL Analyst. */
export default function SqlPage() {
  return <SqlView />;
}
