import { AppShell } from "../layout/AppShell";
import { ProductMicrostructureChart } from "../chart/ProductMicrostructureChart";
import { InspectionStrip } from "../chart/InspectionStrip";
import { ControlPanel } from "../controls/ControlPanel";
import { DashboardHeader } from "./DashboardHeader";
import { useDashboard } from "../../state/DashboardProvider";
import { HoverInspectorPanel } from "../panels/HoverInspectorPanel";
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
          <ProductMicrostructureChart />
          <InspectionStrip />
          <div className="dashboard-main__grid">
            <PnlPanel />
            <PositionPanel />
          </div>
          {isSubmissionMode ? <ProductPerformancePanel /> : null}
          {isSubmissionMode ? <TradeTapePanel /> : null}
        </div>
      }
      secondary={
        <div className="stack">
          <HoverInspectorPanel />
          <TutorialOverviewPanel />
          <InspectionPanel />
          <LogsPanel />
        </div>
      }
    />
  );
}
