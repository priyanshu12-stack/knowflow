import type { Metadata } from "next";

import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Models & Settings" };

/** DRD §7.6 Models & Settings. */
export default function SettingsPage() {
  return <SettingsView />;
}
