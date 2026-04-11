import type {
  BookLevel,
  BookSnapshot,
  IndicatorSeries,
  LogEntry,
  MarketDataset,
  OwnTrade,
  PnLPoint,
  PositionPoint,
  Product,
  Trade,
} from "../../types/market";

const products: Product[] = [
  { id: "AMETHYSTS", symbol: "AMETHYSTS", displayName: "Amethysts", tickSize: 1 },
  { id: "STARFRUIT", symbol: "STARFRUIT", displayName: "Starfruit", tickSize: 1 },
];

const timestamps = Array.from({ length: 90 }, (_, index) => index * 1000);

function createSideLevels(anchorPrice: number, timestampIndex: number, side: "bid" | "ask"): BookLevel[] {
  const drift = Math.sin(timestampIndex / 7) * 2 + Math.cos(timestampIndex / 11);
  const direction = side === "bid" ? -1 : 1;

  return [1, 2, 3].map((level) => ({
    level,
    side,
    price: anchorPrice + direction * (2 + (level - 1) * 2) + drift,
    quantity: 6 + level * 2 + (timestampIndex % (4 + level)),
  }));
}

function createBookSnapshots(productId: string, anchorPrice: number): BookSnapshot[] {
  return timestamps.map((timestamp, index) => ({
    timestamp,
    productId,
    bids: createSideLevels(anchorPrice, index, "bid"),
    asks: createSideLevels(anchorPrice, index, "ask"),
  }));
}

function createTrades(productId: string, anchorPrice: number): Trade[] {
  return timestamps
    .filter((_, index) => index % 3 !== 1)
    .map((timestamp, index) => ({
      id: `${productId}-trade-${timestamp}`,
      timestamp,
      productId,
      price: anchorPrice + Math.sin(index / 4) * 3 + (index % 4) - 1.5,
      quantity: 1 + (index % 6),
      side: index % 2 === 0 ? "buy" : "sell",
      aggressor: index % 2 === 0 ? "buyer" : "seller",
      traderId: index % 6 === 0 ? "desk-alpha" : index % 4 === 0 ? "desk-beta" : "market-passive",
      traderGroup: index % 6 === 0 ? "internal" : index % 4 === 0 ? "hedge-fund" : "exchange-flow",
      tradeType: index % 3 === 0 ? "maker" : "taker",
    }));
}

function createOwnTrades(productId: string, anchorPrice: number): OwnTrade[] {
  return timestamps
    .filter((_, index) => index % 12 === 0)
    .map((timestamp, index) => ({
      id: `${productId}-own-${timestamp}`,
      timestamp,
      productId,
      price: anchorPrice + Math.cos(index / 2) * 2,
      quantity: 2 + (index % 4),
      side: index % 2 === 0 ? "buy" : "sell",
      aggressor: index % 2 === 0 ? "buyer" : "seller",
      traderId: "our-strategy",
      traderGroup: "internal",
      tradeType: "maker",
      strategyTag: "tutorial-maker-v1",
    }));
}

function createIndicatorSeries(baseTimestamps: number[], anchorPrice: number): IndicatorSeries[] {
  return [
    {
      id: "mid-price",
      label: "Mid Price",
      color: "#f4c95d",
      points: baseTimestamps.map((timestamp, index) => ({
        timestamp,
        value: anchorPrice + Math.sin(index / 6) * 2,
      })),
    },
    {
      id: "fair-value",
      label: "Fair Value",
      color: "#58a6ff",
      points: baseTimestamps.map((timestamp, index) => ({
        timestamp,
        value: anchorPrice + Math.cos(index / 9) * 1.5,
      })),
    },
  ];
}

function createPnlSeries(baseTimestamps: number[], productIndex: number): PnLPoint[] {
  return baseTimestamps.map((timestamp, index) => ({
    timestamp,
    value: Math.sin(index / 8) * 12 + productIndex * 20 + index * 0.2,
  }));
}

function createPositionSeries(baseTimestamps: number[], productIndex: number): PositionPoint[] {
  return baseTimestamps.map((timestamp, index) => ({
    timestamp,
    value: Math.round(Math.sin(index / 10 + productIndex) * 8),
  }));
}

function createLogs(productId: string): LogEntry[] {
  return timestamps.filter((_, index) => index % 15 === 0).map((timestamp, index) => ({
    id: `${productId}-log-${timestamp}`,
    timestamp,
    productId,
    level: index % 4 === 0 ? "warning" : "info",
    source: "strategy",
    message:
      index % 4 === 0
        ? `Inventory skew widened around ${timestamp / 1000}s.`
        : `Observed liquidity rotation near best quotes at ${timestamp / 1000}s.`,
  }));
}

export const mockDataset: MarketDataset = {
  id: "mock-session-01",
  name: "Mock Prosperity Session",
  description: "Synthetic multi-product market tape with snapshots, trades, own trades, and placeholder analytics.",
  source: "mock",
  createdAt: new Date("2026-04-10T00:00:00Z").toISOString(),
  products: products.map((product, index) => {
    const anchorPrice = index === 0 ? 10000 : 5000;
    return {
      product,
      bookSnapshots: createBookSnapshots(product.id, anchorPrice),
      trades: createTrades(product.id, anchorPrice),
      ownTrades: createOwnTrades(product.id, anchorPrice),
      pnlSeries: createPnlSeries(timestamps, index),
      positionSeries: createPositionSeries(timestamps, index),
      indicators: createIndicatorSeries(timestamps, anchorPrice),
      logs: createLogs(product.id),
    };
  }),
  metadata: {
    snapshotCount: timestamps.length * products.length,
    tradeCount: products.reduce((sum, product, index) => sum + createTrades(product.id, index === 0 ? 10000 : 5000).length, 0),
    ownTradeCount: products.reduce((sum, product, index) => sum + createOwnTrades(product.id, index === 0 ? 10000 : 5000).length, 0),
  },
};
