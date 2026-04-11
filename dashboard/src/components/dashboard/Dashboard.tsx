import { AppShell } from "../layout/AppShell";
import { MarketChart } from "../chart/MarketChart";
import { InspectionStrip } from "../chart/InspectionStrip";
import { ControlPanel } from "../controls/ControlPanel";
import { DashboardHeader } from "./DashboardHeader";
import { InspectionPanel } from "../panels/InspectionPanel";
import { LogsPanel } from "../panels/LogsPanel";
import { TutorialOverviewPanel } from "../panels/TutorialOverviewPanel";
import { PnlPanel } from "../panels/PnlPanel";
import { PositionPanel } from "../panels/PositionPanel";

export function Dashboard() {
  return (
    <AppShell
      header={<DashboardHeader />}
      sidebar={<ControlPanel />}
      main={
        <div className="dashboard-main">
          <MarketChart />
          <InspectionStrip />
          <div className="dashboard-main__grid">
            <PnlPanel />
            <PositionPanel />
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
