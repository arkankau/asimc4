import { AppShell } from "../layout/AppShell";
import { MarketChart } from "../chart/MarketChart";
import { ControlPanel } from "../controls/ControlPanel";
import { DashboardHeader } from "./DashboardHeader";
import { InspectionPanel } from "../panels/InspectionPanel";
import { PlaceholderMetricPanel } from "../panels/PlaceholderMetricPanel";
import { LogsPanel } from "../panels/LogsPanel";
import { TutorialOverviewPanel } from "../panels/TutorialOverviewPanel";
import { PnlPanel } from "../panels/PnlPanel";

export function Dashboard() {
  return (
    <AppShell
      header={<DashboardHeader />}
      sidebar={<ControlPanel />}
      main={
        <div className="dashboard-main">
          <MarketChart />
          <div className="dashboard-main__grid">
            <PnlPanel />
            <PlaceholderMetricPanel
              title="Position"
              summary="Position state placeholder"
              note="Tutorial stage files do not include inventory, but this slot is ready for strategy or trader position timelines."
            />
          </div>
        </div>
      }
      secondary={
        <div className="stack">
          <TutorialOverviewPanel />
          <InspectionPanel />
          <LogsPanel />
        </div>
      }
    />
  );
}
