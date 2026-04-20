import type { DashboardAction, DashboardInspectionState, DashboardState } from "../types/dashboard";
import type { TraderClass } from "../types/market";

const DEFAULT_TRADER_CLASSES: TraderClass[] = ["M", "S", "B", "I", "F"];

export const emptyInspectionState: DashboardInspectionState = {
  hoveredTimestamp: null,
  hoveredProductId: null,
  hoveredEvent: null,
  hoveredEventType: null,
  hoveredPrice: null,
  hoveredQuantity: null,
  nearestVisibleBid: null,
  nearestVisibleAsk: null,
  nearestVisibleTrade: null,
  nearestVisibleOwnTrade: null,
  visibleTradesAtHoveredTimestamp: [],
  visibleOwnTradesAtHoveredTimestamp: [],
  activeFilterSummary: [],
};

export const initialDashboardState: DashboardState = {
  selectedDatasetId: null,
  selectedProductId: null,
  visibility: {
    bids: true,
    asks: true,
    trades: true,
    ownTrades: true,
  },
  overlays: {
    enabledIndicators: [],
    normalizationMode: "raw",
    downsamplingMode: "none",
    depthLevels: [1, 2, 3],
  },
  filters: {
    selectedTraderClasses: DEFAULT_TRADER_CLASSES,
    selectedTraderGroups: [],
    selectedTraderIds: [],
    quantityRange: null,
  },
  chartViewport: null,
  inspection: emptyInspectionState,
};

export function dashboardReducer(state: DashboardState, action: DashboardAction): DashboardState {
  switch (action.type) {
    case "setDataset":
      return {
        ...state,
        selectedDatasetId: action.datasetId,
        selectedProductId: null,
        chartViewport: null,
        inspection: emptyInspectionState,
      };
    case "setProduct":
      return {
        ...state,
        selectedProductId: action.productId,
        chartViewport: null,
        inspection: emptyInspectionState,
      };
    case "setInspection":
      return {
        ...state,
        inspection: action.inspection,
      };
    case "clearInspection":
      return {
        ...state,
        inspection: emptyInspectionState,
      };
    case "toggleVisibility":
      return {
        ...state,
        visibility: {
          ...state.visibility,
          [action.key]: !state.visibility[action.key],
        },
      };
    case "setIndicatorEnabled":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          enabledIndicators: action.enabled
            ? [...new Set([...state.overlays.enabledIndicators, action.indicatorId])]
            : state.overlays.enabledIndicators.filter((id) => id !== action.indicatorId),
        },
      };
    case "setNormalizationMode":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          normalizationMode: action.mode,
        },
      };
    case "setDownsamplingMode":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          downsamplingMode: action.mode,
        },
      };
    case "setDepthLevels":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          depthLevels: action.levels,
        },
      };
    case "setSelectedTraderClasses":
      return {
        ...state,
        filters: {
          ...state.filters,
          selectedTraderClasses: action.traderClasses,
        },
      };
    case "setSelectedTraderGroups":
      return {
        ...state,
        filters: {
          ...state.filters,
          selectedTraderGroups: action.traderGroups,
        },
      };
    case "setSelectedTraderIds":
      return {
        ...state,
        filters: {
          ...state.filters,
          selectedTraderIds: action.traderIds,
        },
      };
    case "setQuantityRange":
      return {
        ...state,
        filters: {
          ...state.filters,
          quantityRange: action.quantityRange,
        },
      };
    case "setChartViewport":
      return {
        ...state,
        chartViewport: action.viewport,
      };
    case "resetChartViewport":
      return {
        ...state,
        chartViewport: null,
      };
    default:
      return state;
  }
}
