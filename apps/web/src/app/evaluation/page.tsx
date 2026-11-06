import type { Metadata } from "next";

import { EvaluationView } from "@/components/evaluation/evaluation-view";

export const metadata: Metadata = { title: "Evaluation Lab" };

/** DRD §7.5 Evaluation Lab. */
export default function EvaluationPage() {
  return <EvaluationView />;
}
