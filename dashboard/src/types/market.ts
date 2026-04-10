export type Timestamp = number;
export type ProductId = string;
export type DatasetId = string;

export type BookSide = "bid" | "ask";
export type TradeSide = "buy" | "sell";
export type DataSourceKind = "mock" | "upload" | "tutorial";

export interface Product {
  id: ProductId;
  symbol: string;
  displayName: string;
  tickSize?: number;
}

export interface OrderBookLevel {
  timestamp: Timestamp;
  productId: ProductId;
  side: BookSide;
  price: number;
  quantity: number;
  level: number;
}

export interface Trade {
  id: string;
  timestamp: Timestamp;
  productId: ProductId;
  price: number;
  quantity: number;
  side: TradeSide;
  aggressor: "buyer" | "seller" | "unknown";
  traderId?: string;
  ownTrade?: boolean;
}

export interface IndicatorPoint {
  timestamp: Timestamp;
  value: number;
}

export interface IndicatorSeries {
  id: string;
  label: string;
  color: string;
  points: IndicatorPoint[];
}

export interface ProductMarketData {
  product: Product;
  orderBook: OrderBookLevel[];
  trades: Trade[];
  indicators: IndicatorSeries[];
}

export interface MarketDataset {
  id: DatasetId;
  name: string;
  description: string;
  source: DataSourceKind;
  createdAt: string;
  products: ProductMarketData[];
  metadata?: DatasetMetadata;
}

export interface DatasetMetadata {
  round?: number;
  day?: number;
  priceSource?: string;
  tradeSource?: string;
  rowCount?: number;
  tradeCount?: number;
}

export interface VisualizationPoint {
  timestamp: Timestamp;
  price: number;
  quantity: number;
  label: string;
  side: BookSide | TradeSide;
  kind: "quote" | "trade";
  level?: number;
}

export interface InspectionSnapshot {
  timestamp: Timestamp | null;
  productId: ProductId | null;
  nearestBid: OrderBookLevel | null;
  nearestAsk: OrderBookLevel | null;
  nearestTrade: Trade | null;
}
