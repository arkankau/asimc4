import type {
  IndicatorSeries,
  MarketDataset,
  OrderBookLevel,
  Product,
  Trade,
} from "../../types/market";

const products: Product[] = [
  { id: "AMETHYSTS", symbol: "AMETHYSTS", displayName: "Amethysts", tickSize: 1 },
  { id: "STARFRUIT", symbol: "STARFRUIT", displayName: "Starfruit", tickSize: 1 },
];

function createIndicatorSeries(baseTimestamps: number[], anchorPrice: number): IndicatorSeries[] {
  return [
    {
      id: "mid-fair-value",
      label: "Fair Value",
      color: "#f4c95d",
      points: baseTimestamps.map((timestamp, index) => ({
        timestamp,
        value: anchorPrice + Math.sin(index / 6) * 2,
      })),
    },
  ];
}

function createBook(productId: string, anchorPrice: number, timestamps: number[]): OrderBookLevel[] {
  return timestamps.flatMap((timestamp, index) => {
    const drift = Math.sin(index / 5) * 2;
    return [
      {
        timestamp,
        productId,
        side: "bid",
        price: anchorPrice - 2 + drift,
        quantity: 10 + (index % 5) * 2,
        level: 1,
      },
      {
        timestamp,
        productId,
        side: "bid",
        price: anchorPrice - 4 + drift,
        quantity: 7 + (index % 4),
        level: 2,
      },
      {
        timestamp,
        productId,
        side: "ask",
        price: anchorPrice + 2 + drift,
        quantity: 11 + (index % 6),
        level: 1,
      },
      {
        timestamp,
        productId,
        side: "ask",
        price: anchorPrice + 4 + drift,
        quantity: 9 + (index % 4),
        level: 2,
      },
    ];
  });
}

function createTrades(productId: string, anchorPrice: number, timestamps: number[]): Trade[] {
  return timestamps
    .filter((_, index) => index % 2 === 0)
    .map((timestamp, index) => ({
      id: `${productId}-trade-${index}`,
      timestamp,
      productId,
      price: anchorPrice + Math.cos(index / 3) * 3 + (index % 3) - 1,
      quantity: 2 + (index % 5),
      side: index % 3 === 0 ? "buy" : "sell",
      aggressor: index % 3 === 0 ? "buyer" : "seller",
      traderId: index % 4 === 0 ? "desk-alpha" : "market",
      ownTrade: index % 7 === 0,
    }));
}

const timestamps = Array.from({ length: 60 }, (_, index) => index * 1000);

export const mockDataset: MarketDataset = {
  id: "mock-session-01",
  name: "Mock Prosperity Session",
  description: "Synthetic multi-product market tape for dashboard MVP development.",
  source: "mock",
  createdAt: new Date("2026-04-10T00:00:00Z").toISOString(),
  products: products.map((product, index) => {
    const anchorPrice = index === 0 ? 10000 : 5000;
    return {
      product,
      orderBook: createBook(product.id, anchorPrice, timestamps),
      trades: createTrades(product.id, anchorPrice, timestamps),
      indicators: createIndicatorSeries(timestamps, anchorPrice),
    };
  }),
};
