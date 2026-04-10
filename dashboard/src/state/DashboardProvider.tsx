import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type Dispatch,
  type PropsWithChildren,
} from "react";
import { datasetRepository } from "../data/loaders/datasetRepository";
import { dashboardReducer, initialDashboardState } from "./dashboardReducer";
import type { DashboardAction, DashboardState } from "../types/dashboard";
import type { InspectionSnapshot, MarketDataset, ProductMarketData } from "../types/market";
import { buildInspectionSnapshot, getDatasetProduct, listProducts } from "../utils/marketSelectors";

interface DashboardContextValue {
  state: DashboardState;
  datasets: MarketDataset[];
  selectedDataset: MarketDataset | null;
  selectedProduct: ProductMarketData | null;
  inspection: InspectionSnapshot;
  dispatch: Dispatch<DashboardAction>;
  importDataset: (file: File) => Promise<void>;
  refreshDatasets: () => Promise<void>;
  availableProducts: ReturnType<typeof listProducts>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(dashboardReducer, initialDashboardState);
  const [datasets, setDatasets] = useState<MarketDataset[]>([]);

  const refreshDatasets = async () => {
    const available = await datasetRepository.listDatasets();
    setDatasets(available);
  };

  useEffect(() => {
    void refreshDatasets();
  }, []);

  useEffect(() => {
    if (!datasets.length) {
      return;
    }

    if (!state.selectedDatasetId) {
      const preferredDataset = datasets.find((dataset) => dataset.source === "tutorial") ?? datasets[0];
      dispatch({ type: "setDataset", datasetId: preferredDataset.id });
      return;
    }

    const selectedDataset = datasets.find((dataset) => dataset.id === state.selectedDatasetId);
    if (selectedDataset && !state.selectedProductId && selectedDataset.products.length > 0) {
      dispatch({ type: "setProduct", productId: selectedDataset.products[0].product.id });
    }
  }, [datasets, state.selectedDatasetId, state.selectedProductId]);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === state.selectedDatasetId) ?? null,
    [datasets, state.selectedDatasetId],
  );

  const availableProducts = useMemo(() => listProducts(selectedDataset), [selectedDataset]);

  const selectedProduct = useMemo(
    () => getDatasetProduct(selectedDataset, state.selectedProductId),
    [selectedDataset, state.selectedProductId],
  );

  const inspection = useMemo(
    () => buildInspectionSnapshot(selectedProduct, state.hoveredTimestamp),
    [selectedProduct, state.hoveredTimestamp],
  );

  const importDataset = async (file: File) => {
    const uploaded = await datasetRepository.importFile(file);
    const available = await datasetRepository.listDatasets();
    setDatasets(available);
    dispatch({ type: "setDataset", datasetId: uploaded.id });

    if (uploaded.products[0]) {
      dispatch({ type: "setProduct", productId: uploaded.products[0].product.id });
    }
  };

  const value = {
    state,
    datasets,
    selectedDataset,
    selectedProduct,
    inspection,
    dispatch,
    importDataset,
    refreshDatasets,
    availableProducts,
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const context = useContext(DashboardContext);

  if (!context) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }

  return context;
}
