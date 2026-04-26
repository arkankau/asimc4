export type Timestamp = number;
export type ProductId = string;
export type DatasetId = string;

export type BookSide = "bid" | "ask";
export type TradeSide = "buy" | "sell";
export type MarketEventKind = "bid" | "ask" | "trade" | "ownTrade";
export type TradeType = "maker" | "taker" | "unknown";
export type TraderClass = "M" | "S" | "B" | "I" | "F";
export type DataSourceKind = "mock" | "upload" | "tutorial" | "historical" | "submission";

export interface Product {
  id: ProductId;
  symbol: string;
  displayName: string;
  tickSize?: number;
}

export interface BookLevel {
  price: number;
  quantity: number;
  level: number;
  side: BookSide;
}

export interface BookSnapshot {
  timestamp: Timestamp;
  productId: ProductId;
  bids: BookLevel[];
  asks: BookLevel[];
}

export interface Trade {
  id: string;
  timestamp: Timestamp;
  productId: ProductId;
  price: number;
  quantity: number;
  side: TradeSide;
  aggressor: "buyer" | "seller" | "unknown";
  buyer?: string;
  seller?: string;
  traderId?: string;
  traderGroup?: string;
  traderClass?: TraderClass;
  tradeType: TradeType;
}

export interface OwnTrade extends Trade {
  strategyTag?: string;
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

export interface PnLPoint {
  timestamp: Timestamp;
  value: number;
}

export interface PositionPoint {
  timestamp: Timestamp;
  value: number;
}

export interface LogEntry {
  id: string;
  timestamp: Timestamp;
  productId: ProductId;
  level: "info" | "warning" | "error";
  source: string;
  message: string;
}

export interface MarketEvent {
  id: string;
  timestamp: Timestamp;
  productId: ProductId;
  kind: MarketEventKind;
  price: number;
  quantity: number;
  label: string;
  level?: number;
  side?: BookSide | TradeSide;
  tradeType?: TradeType;
  buyer?: string;
  seller?: string;
  traderId?: string;
  traderGroup?: string;
  traderClass?: TraderClass;
}

export interface ProductMarketData {
  product: Product;
  bookSnapshots: BookSnapshot[];
  trades: Trade[];
  ownTrades: OwnTrade[];
  pnlSeries: PnLPoint[];
  positionSeries: PositionPoint[];
  indicators: IndicatorSeries[];
  logs: LogEntry[];
}

export interface DatasetMetadata {
  round?: number;
  day?: number;
  submissionId?: string;
  resultStatus?: string;
  reportedProfit?: number;
  priceSource?: string;
  tradeSource?: string;
  snapshotCount?: number;
  tradeCount?: number;
  ownTradeCount?: number;
  logCount?: number;
  rowCount?: number;
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

export interface ChartViewport {
  minTimestamp: Timestamp;
  maxTimestamp: Timestamp;
  minPrice: number;
  maxPrice: number;
}

export interface ChartSeriesBundle {
  visibleBids: MarketEvent[];
  visibleAsks: MarketEvent[];
  visibleTrades: MarketEvent[];
  visibleOwnTrades: MarketEvent[];
  visibleEvents: MarketEvent[];
  visibleIndicators: IndicatorSeries[];
  fullBounds: ChartViewport;
  viewport: ChartViewport;
  filterSummary: string[];
}

export interface TradeFilterSupport {
  availableTraderIds: string[];
  availableTraderGroups: string[];
  availableTraderClasses: TraderClass[];
  traderClassCounts: Record<TraderClass, number>;
  supportsTraderIds: boolean;
  supportsTraderGroups: boolean;
  minTradeQuantity: number | null;
  maxTradeQuantity: number | null;
  bigTradeThreshold: number | null;
  usesInferredTraderClasses: boolean;
}
