import { CurrentDate } from "@/components/overview/current-date";
import { ReadinessPanel } from "@/components/system-status/readiness-panel";

/**
 * DRD §7.1 Overview. Only regions backed by real data are shown: document metrics, activity
 * and quick actions appear once their features exist (M1+), never as placeholder counts.
 */
export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-8">
      <header>
        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
          <CurrentDate />
        </p>
        <h1 className="mt-1 text-[26px] leading-tight font-semibold tracking-tight">
          Workspace overview
        </h1>
        <p className="mt-1.5 max-w-prose text-[15px] text-muted-foreground">
          KnowFlow runs entirely on this machine. Check that the database and local models are ready
          before adding documents.
        </p>
      </header>
      <ReadinessPanel />
    </div>
  );
}
