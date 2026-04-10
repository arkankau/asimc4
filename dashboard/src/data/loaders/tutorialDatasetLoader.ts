import type {
  IndicatorSeries,
  MarketDataset,
  OrderBookLevel,
  ProductMarketData,
  Trade,
} from "../../types/market";

interface TutorialDatasetFileConfig {
  id: string;
  name: string;
  description: string;
  day: number;
  round: number;
  pricesPath: string;
  tradesPath: string;
}

interface TutorialPriceRow {
  day: number;
  timestamp: number;
  product: string;
  bid_price_1?: number;
  bid_volume_1?: number;
  bid_price_2?: number;
  bid_volume_2?: number;
  bid_price_3?: number;
  bid_volume_3?: number;
  ask_price_1?: number;
  ask_volume_1?: number;
  ask_price_2?: number;
  ask_volume_2?: number;
  ask_price_3?: number;
  ask_volume_3?: number;
  mid_price?: number;
  profit_and_loss?: number;
}

interface TutorialTradeRow {
  timestamp: number;
  buyer?: string;
  seller?: string;
  symbol: string;
  currency: string;
  price: number;
  quantity: number;
}

const tutorialDatasetConfigs: TutorialDatasetFileConfig[] = [
  {
    id: "tutorial-round-0-day--2",
    name: "Tutorial Stage Day -2",
    description: "Round 0 tutorial order book and trades for day -2.",
    day: -2,
    round: 0,
    pricesPath: "/tutorial/data/prices_round_0_day_-2.csv",
    tradesPath: "/tutorial/data/trades_round_0_day_-2.csv",
  },
  {
    id: "tutorial-round-0-day--1",
    name: "Tutorial Stage Day -1",
    description: "Round 0 tutorial order book and trades for day -1.",
    day: -1,
    round: 0,
    pricesPath: "/tutorial/data/prices_round_0_day_-1.csv",
    tradesPath: "/tutorial/data/trades_round_0_day_-1.csv",
  },
];

function parseNumber(value: string | undefined) {
  if (!value || value.trim() === "") {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseDelimitedCsv<T extends Record<string, string | number | undefined>>(text: string): T[] {
  const lines = text.trim().split(/\r?\n/);
  const [headerLine, ...rows] = lines;

  if (!headerLine) {
    return [];
  }

  const headers = headerLine.split(";").map((column) => column.trim());

  return rows
    .filter((row) => row.trim().length > 0)
    .map((row) => {
      const values = row.split(";");
      return Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim()])) as T;
    });
}

function inferTradeSide(price: number, bidPrice?: number, askPrice?: number) {
  if (askPrice !== undefined && price >= askPrice) {
    return { side: "buy" as const, aggressor: "buyer" as const };
  }

  if (bidPrice !== undefined && price <= bidPrice) {
    return { side: "sell" as const, aggressor: "seller" as const };
  }

  return { side: "buy" as const, aggressor: "unknown" as const };
}

function findNearestPriceRow(rows: TutorialPriceRow[], timestamp: number) {
  return rows.reduce<TutorialPriceRow | null>((closest, row) => {
    if (!closest) {
      return row;
    }

    return Math.abs(row.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? row : closest;
  }, null);
}

function buildIndicators(rows: TutorialPriceRow[]): IndicatorSeries[] {
  const midPricePoints = rows
    .filter((row) => row.mid_price !== undefined)
    .map((row) => ({
      timestamp: row.timestamp,
      value: row.mid_price!,
    }));

  const pnlPoints = rows
    .filter((row) => row.profit_and_loss !== undefined)
    .map((row) => ({
      timestamp: row.timestamp,
      value: row.profit_and_loss!,
    }));

  return [
    {
      id: "mid-price",
      label: "Mid Price",
      color: "#f4c95d",
      points: midPricePoints,
    },
    {
      id: "tutorial-pnl",
      label: "Profit and Loss",
      color: "#58a6ff",
      points: pnlPoints,
    },
  ];
}

function buildOrderBook(rows: TutorialPriceRow[]): OrderBookLevel[] {
  const levels: OrderBookLevel[] = [];

  for (const row of rows) {
    for (const level of [1, 2, 3] as const) {
      const bidPrice = row[`bid_price_${level}` as keyof TutorialPriceRow] as number | undefined;
      const bidVolume = row[`bid_volume_${level}` as keyof TutorialPriceRow] as number | undefined;
      const askPrice = row[`ask_price_${level}` as keyof TutorialPriceRow] as number | undefined;
      const askVolume = row[`ask_volume_${level}` as keyof TutorialPriceRow] as number | undefined;

      if (bidPrice !== undefined && bidVolume !== undefined) {
        levels.push({
          timestamp: row.timestamp,
          productId: row.product,
          side: "bid",
          price: bidPrice,
          quantity: bidVolume,
          level,
        });
      }

      if (askPrice !== undefined && askVolume !== undefined) {
        levels.push({
          timestamp: row.timestamp,
          productId: row.product,
          side: "ask",
          price: askPrice,
          quantity: Math.abs(askVolume),
          level,
        });
      }
    }
  }

  return levels;
}

function parsePriceRows(text: string) {
  const rows = parseDelimitedCsv<Record<string, string>>(text);

  return rows.map<TutorialPriceRow>((row) => ({
    day: Number(row.day),
    timestamp: Number(row.timestamp),
    product: row.product,
    bid_price_1: parseNumber(row.bid_price_1),
    bid_volume_1: parseNumber(row.bid_volume_1),
    bid_price_2: parseNumber(row.bid_price_2),
    bid_volume_2: parseNumber(row.bid_volume_2),
    bid_price_3: parseNumber(row.bid_price_3),
    bid_volume_3: parseNumber(row.bid_volume_3),
    ask_price_1: parseNumber(row.ask_price_1),
    ask_volume_1: parseNumber(row.ask_volume_1),
    ask_price_2: parseNumber(row.ask_price_2),
    ask_volume_2: parseNumber(row.ask_volume_2),
    ask_price_3: parseNumber(row.ask_price_3),
    ask_volume_3: parseNumber(row.ask_volume_3),
    mid_price: parseNumber(row.mid_price),
    profit_and_loss: parseNumber(row.profit_and_loss),
  }));
}

function parseTradeRows(text: string) {
  const rows = parseDelimitedCsv<Record<string, string>>(text);

  return rows.map<TutorialTradeRow>((row) => ({
    timestamp: Number(row.timestamp),
    buyer: row.buyer || undefined,
    seller: row.seller || undefined,
    symbol: row.symbol,
    currency: row.currency,
    price: Number(row.price),
    quantity: Number(row.quantity),
  }));
}

function createProductData(productId: string, priceRows: TutorialPriceRow[], tradeRows: TutorialTradeRow[]): ProductMarketData {
  const sortedRows = [...priceRows].sort((a, b) => a.timestamp - b.timestamp);
  const orderBook = buildOrderBook(sortedRows);

  const trades: Trade[] = tradeRows.map((trade, index) => {
    const referenceRow = findNearestPriceRow(sortedRows, trade.timestamp);
    const sideInfo = inferTradeSide(trade.price, referenceRow?.bid_price_1, referenceRow?.ask_price_1);

    return {
      id: `${productId}-trade-${trade.timestamp}-${index}`,
      timestamp: trade.timestamp,
      productId,
      price: trade.price,
      quantity: trade.quantity,
      side: sideInfo.side,
      aggressor: sideInfo.aggressor,
      traderId: trade.buyer || trade.seller || trade.currency || undefined,
      ownTrade: Boolean(trade.buyer || trade.seller),
    };
  });

  return {
    product: {
      id: productId,
      symbol: productId,
      displayName: productId,
      tickSize: 1,
    },
    orderBook,
    trades,
    indicators: buildIndicators(sortedRows),
  };
}

export async function loadTutorialDatasets(): Promise<MarketDataset[]> {
  const datasets = await Promise.all(
    tutorialDatasetConfigs.map(async (config) => {
      const [pricesResponse, tradesResponse] = await Promise.all([
        fetch(config.pricesPath),
        fetch(config.tradesPath),
      ]);

      if (!pricesResponse.ok || !tradesResponse.ok) {
        throw new Error(`Failed to load tutorial files for ${config.name}.`);
      }

      const [pricesText, tradesText] = await Promise.all([pricesResponse.text(), tradesResponse.text()]);
      const priceRows = parsePriceRows(pricesText);
      const tradeRows = parseTradeRows(tradesText);

      const productIds = [...new Set(priceRows.map((row) => row.product))];
      const products = productIds.map((productId) =>
        createProductData(
          productId,
          priceRows.filter((row) => row.product === productId),
          tradeRows.filter((row) => row.symbol === productId),
        ),
      );

      return {
        id: config.id,
        name: config.name,
        description: config.description,
        source: "tutorial" as const,
        createdAt: new Date().toISOString(),
        products,
        metadata: {
          round: config.round,
          day: config.day,
          priceSource: config.pricesPath,
          tradeSource: config.tradesPath,
          rowCount: priceRows.length,
          tradeCount: tradeRows.length,
        },
      };
    }),
  );

  return datasets;
}
