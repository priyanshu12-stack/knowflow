import type { Metadata } from "next";

import { ActivityView } from "@/components/activity/activity-view";

export const metadata: Metadata = { title: "Activity" };

/** PRD §4 Activity / Logs. */
export default function ActivityPage() {
  return <ActivityView />;
}
