import type {
  InspectionSnapshot,
  MarketDataset,
  OrderBookLevel,
  Product,
  ProductMarketData,
  Timestamp,
  Trade,
  VisualizationPoint,
} from "../types/market";
import type { DashboardState } from "../types/dashboard";

function nearestByTimestamp<T extends { timestamp: number }>(items: T[], timestamp: Timestamp | null): T | null {
  if (timestamp === null || items.length === 0) {
    return null;
  }

  return items.reduce<T | null>((closest, current) => {
    if (!closest) {
      return current;
    }

    return Math.abs(current.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? current : closest;
  }, null);
}

export function listProducts(dataset: MarketDataset | null): Product[] {
  return dataset?.products.map((entry) => entry.product) ?? [];
}

export function getDatasetProduct(dataset: MarketDataset | null, productId: string | null): ProductMarketData | null {
  if (!dataset || !productId) {
    return null;
  }

  return dataset.products.find((entry) => entry.product.id === productId) ?? null;
}

export function buildInspectionSnapshot(
  product: ProductMarketData | null,
  hoveredTimestamp: Timestamp | null,
): InspectionSnapshot {
  const bids = product?.orderBook.filter((level) => level.side === "bid") ?? [];
  const asks = product?.orderBook.filter((level) => level.side === "ask") ?? [];

  return {
    timestamp: hoveredTimestamp,
    productId: product?.product.id ?? null,
    nearestBid: nearestByTimestamp(bids, hoveredTimestamp),
    nearestAsk: nearestByTimestamp(asks, hoveredTimestamp),
    nearestTrade: nearestByTimestamp(product?.trades ?? [], hoveredTimestamp),
  };
}

export function buildVisualizationPoints(
  product: ProductMarketData | null,
  state: DashboardState,
): VisualizationPoint[] {
  if (!product) {
    return [];
  }

  const depthLevels = new Set(state.overlays.depthLevels);
  const quantityRange = state.filters.quantityRange;

  const passQuantity = (quantity: number) =>
    !quantityRange || (quantity >= quantityRange[0] && quantity <= quantityRange[1]);

  const quotes = product.orderBook
    .filter((level) => depthLevels.has(level.level))
    .filter((level) => passQuantity(level.quantity))
    .filter((level) => {
      if (level.side === "bid") {
        return state.visibility.bids;
      }
      return state.visibility.asks;
    })
    .map<VisualizationPoint>((level) => ({
      timestamp: level.timestamp,
      price: level.price,
      quantity: level.quantity,
      side: level.side,
      kind: "quote",
      label: `${level.side.toUpperCase()} L${level.level}`,
      level: level.level,
    }));

  const trades = product.trades
    .filter((trade) => state.visibility.trades)
    .filter((trade) => passQuantity(trade.quantity))
    .filter((trade) => {
      if (state.filters.traderIds.length === 0) {
        return true;
      }
      return trade.traderId ? state.filters.traderIds.includes(trade.traderId) : false;
    })
    .map<VisualizationPoint>((trade) => ({
      timestamp: trade.timestamp,
      price: trade.price,
      quantity: trade.quantity,
      side: trade.side,
      kind: "trade",
      label: trade.ownTrade ? "Own trade" : `${trade.side.toUpperCase()} trade`,
    }));

  return [...quotes, ...trades].sort((a, b) => a.timestamp - b.timestamp);
}

export function collectChartBounds(points: VisualizationPoint[]) {
  if (points.length === 0) {
    return {
      minTimestamp: 0,
      maxTimestamp: 1,
      minPrice: 0,
      maxPrice: 1,
    };
  }

  const timestamps = points.map((point) => point.timestamp);
  const prices = points.map((point) => point.price);

  return {
    minTimestamp: Math.min(...timestamps),
    maxTimestamp: Math.max(...timestamps),
    minPrice: Math.min(...prices),
    maxPrice: Math.max(...prices),
  };
}

export function groupQuotesBySide(levels: OrderBookLevel[]) {
  return {
    bids: levels.filter((level) => level.side === "bid"),
    asks: levels.filter((level) => level.side === "ask"),
  };
}

export function listUniqueTraders(trades: Trade[]) {
  return [...new Set(trades.map((trade) => trade.traderId).filter(Boolean) as string[])];
}
