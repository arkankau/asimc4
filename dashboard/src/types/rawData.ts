export interface RawFlatMarketRow {
  timestamp: string;
  productId: string;
  kind: string;
  side?: string;
  price?: string;
  quantity?: string;
  level?: string;
  id?: string;
  aggressor?: string;
  traderId?: string;
  ownTrade?: string;
}

export interface RawTutorialPriceRow {
  day: string;
  timestamp: string;
  product: string;
  bid_price_1?: string;
  bid_volume_1?: string;
  bid_price_2?: string;
  bid_volume_2?: string;
  bid_price_3?: string;
  bid_volume_3?: string;
  ask_price_1?: string;
  ask_volume_1?: string;
  ask_price_2?: string;
  ask_volume_2?: string;
  ask_price_3?: string;
  ask_volume_3?: string;
  mid_price?: string;
  profit_and_loss?: string;
}

export interface RawTutorialTradeRow {
  timestamp: string;
  buyer?: string;
  seller?: string;
  symbol: string;
  currency: string;
  price: string;
  quantity: string;
}

export interface RawSubmissionTradeRow {
  timestamp: number;
  buyer?: string;
  seller?: string;
  symbol: string;
  currency?: string;
  price: number;
  quantity: number;
}

export interface RawSubmissionLogRow {
  timestamp: number;
  sandboxLog?: string;
  lambdaLog?: string;
}

export interface RawSubmissionPositionRow {
  symbol: string;
  quantity: number;
}

export interface RawSubmissionResultPayload {
  submissionId?: string;
  round?: string;
  status?: string;
  profit?: number;
  activitiesLog?: string;
  graphLog?: string;
  tradeHistory?: RawSubmissionTradeRow[];
  logs?: RawSubmissionLogRow[];
  positions?: RawSubmissionPositionRow[];
}
