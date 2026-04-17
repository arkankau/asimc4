import { AppShell } from "../layout/AppShell";
import { BacktestChart } from "../chart/BacktestChart";
import { MarketChart } from "../chart/MarketChart";
import { InspectionStrip } from "../chart/InspectionStrip";
import { ControlPanel } from "../controls/ControlPanel";
import { DashboardHeader } from "./DashboardHeader";
import { useDashboard } from "../../state/DashboardProvider";
import { InspectionPanel } from "../panels/InspectionPanel";
import { LogsPanel } from "../panels/LogsPanel";
import { TutorialOverviewPanel } from "../panels/TutorialOverviewPanel";
import { PnlPanel } from "../panels/PnlPanel";
import { PositionPanel } from "../panels/PositionPanel";
import { ProductPerformancePanel } from "../panels/ProductPerformancePanel";
import { TradeTapePanel } from "../panels/TradeTapePanel";

export function Dashboard() {
  const { selectedDataset } = useDashboard();
  const isSubmissionMode = selectedDataset?.source === "submission";

  return (
    <AppShell
      header={<DashboardHeader />}
      sidebar={<ControlPanel />}
      main={
        <div className="dashboard-main">
          {isSubmissionMode ? (
            <>
              <BacktestChart />
              <div className="dashboard-main__grid">
                <PnlPanel />
                <PositionPanel />
              </div>
              <ProductPerformancePanel />
              <TradeTapePanel />
            </>
          ) : (
            <>
              <MarketChart />
              <InspectionStrip />
              <div className="dashboard-main__grid">
                <PnlPanel />
                <PositionPanel />
              </div>
            </>
          )}
        </div>
      }
      secondary={
        <div className="stack">
          <TutorialOverviewPanel />
          {isSubmissionMode ? null : <InspectionPanel />}
          <LogsPanel />
        </div>
      }
    />
  );
}
