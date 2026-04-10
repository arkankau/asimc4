import { Dashboard } from "../components/dashboard/Dashboard";
import { DashboardProvider } from "../state/DashboardProvider";

export function App() {
  return (
    <DashboardProvider>
      <Dashboard />
    </DashboardProvider>
  );
}
