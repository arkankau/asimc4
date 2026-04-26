import type {
  BookLevel,
  BookSnapshot,
  DataSourceKind,
  IndicatorSeries,
  LogEntry,
  MarketDataset,
  OwnTrade,
  PnLPoint,
  PositionPoint,
  ProductMarketData,
  Trade,
} from "../../types/market";
import type {
  RawTutorialPriceRow,
  RawTutorialTradeRow,
} from "../../types/rawData";

interface TutorialDatasetFileConfig {
  id: string;
  name: string;
  description: string;
  source: DataSourceKind;
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
    source: "tutorial",
    day: -2,
    round: 0,
    pricesPath: "/tutorial/data/prices_round_0_day_-2.csv",
    tradesPath: "/tutorial/data/trades_round_0_day_-2.csv",
  },
  {
    id: "tutorial-round-0-day--1",
    name: "Tutorial Stage Day -1",
    description: "Round 0 tutorial order book and trades for day -1.",
    source: "tutorial",
    day: -1,
    round: 0,
    pricesPath: "/tutorial/data/prices_round_0_day_-1.csv",
    tradesPath: "/tutorial/data/trades_round_0_day_-1.csv",
  },
  {
    id: "historical-round-2-day--1",
    name: "Round 2 Market Data Day -1",
    description: "Round 2 historical order book and trades for day -1.",
    source: "historical",
    day: -1,
    round: 2,
    pricesPath: "/round2/data/prices_round_2_day_-1.csv",
    tradesPath: "/round2/data/trades_round_2_day_-1.csv",
  },
  {
    id: "historical-round-2-day-0",
    name: "Round 2 Market Data Day 0",
    description: "Round 2 historical order book and trades for day 0.",
    source: "historical",
    day: 0,
    round: 2,
    pricesPath: "/round2/data/prices_round_2_day_0.csv",
    tradesPath: "/round2/data/trades_round_2_day_0.csv",
  },
  {
    id: "historical-round-2-day-1",
    name: "Round 2 Market Data Day 1",
    description: "Round 2 historical order book and trades for day 1.",
    source: "historical",
    day: 1,
    round: 2,
    pricesPath: "/round2/data/prices_round_2_day_1.csv",
    tradesPath: "/round2/data/trades_round_2_day_1.csv",
  },
];

function parseNumber(value: string | undefined) {
  if (!value || value.trim() === "") {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseDelimitedCsv(
  text: string
): Array<Record<string, string | undefined>> {
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
      return Object.fromEntries(
        headers.map((header, index) => [header, values[index]?.trim()])
      );
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

    return Math.abs(row.timestamp - timestamp) <
      Math.abs(closest.timestamp - timestamp)
      ? row
      : closest;
  }, null);
}

function buildSideLevels(
  row: TutorialPriceRow,
  side: "bid" | "ask"
): BookLevel[] {
  return ([1, 2, 3] as const)
    .map((level) => {
      const price = row[`${side}_price_${level}` as keyof TutorialPriceRow] as
        | number
        | undefined;
      const quantity = row[
        `${side}_volume_${level}` as keyof TutorialPriceRow
      ] as number | undefined;

      if (price === undefined || quantity === undefined) {
        return null;
      }

      return {
        level,
        side,
        price,
        quantity: Math.abs(quantity),
      };
    })
    .filter(Boolean) as BookLevel[];
}

function buildSnapshots(rows: TutorialPriceRow[]): BookSnapshot[] {
  return rows
    .sort((left, right) => left.timestamp - right.timestamp)
    .map((row) => ({
      timestamp: row.timestamp,
      productId: row.product,
      bids: buildSideLevels(row, "bid"),
      asks: buildSideLevels(row, "ask"),
    }));
}

function buildIndicators(rows: TutorialPriceRow[]): IndicatorSeries[] {
  return [
    {
      id: "mid-price",
      label: "Mid Price",
      color: "#f4c95d",
      points: rows
        .filter((row) => row.mid_price !== undefined)
        .map((row) => ({ timestamp: row.timestamp, value: row.mid_price! })),
    },
  ];
}

function buildPnlSeries(rows: TutorialPriceRow[]): PnLPoint[] {
  return rows
    .filter((row) => row.profit_and_loss !== undefined)
    .map((row) => ({
      timestamp: row.timestamp,
      value: row.profit_and_loss!,
    }));
}

function buildPositionSeries(rows: TutorialPriceRow[]): PositionPoint[] {
  return rows.map((row, index) => ({
    timestamp: row.timestamp,
    value: index === 0 ? 0 : Math.round(Math.sin(index / 18) * 2),
  }));
}

function buildLogs(productId: string, rows: TutorialPriceRow[]): LogEntry[] {
  return rows
    .filter((_, index) => index % 30 === 0)
    .map((row, index) => ({
      id: `${productId}-tutorial-log-${row.timestamp}`,
      timestamp: row.timestamp,
      productId,
      level: "info",
      source: "tutorial-adapter",
      message:
        index % 2 === 0
          ? `Imported tutorial book snapshot for ${productId} at ${
              row.timestamp / 1000
            }s.`
          : `No external log file yet; this placeholder is generated from normalized tutorial data.`,
    }));
}

function parsePriceRows(text: string) {
  const rows = parseDelimitedCsv(text) as unknown as RawTutorialPriceRow[];

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
  const rows = parseDelimitedCsv(text) as unknown as RawTutorialTradeRow[];

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

function createProductData(
  productId: string,
  priceRows: TutorialPriceRow[],
  tradeRows: TutorialTradeRow[]
): ProductMarketData {
  const sortedRows = [...priceRows].sort((a, b) => a.timestamp - b.timestamp);
  const trades: Trade[] = tradeRows.map((trade, index) => {
    const referenceRow = findNearestPriceRow(sortedRows, trade.timestamp);
    const sideInfo = inferTradeSide(
      trade.price,
      referenceRow?.bid_price_1,
      referenceRow?.ask_price_1
    );

    return {
      id: `${productId}-trade-${trade.timestamp}-${index}`,
      timestamp: trade.timestamp,
      productId,
      price: trade.price,
      quantity: trade.quantity,
      side: sideInfo.side,
      aggressor: sideInfo.aggressor,
      traderId: trade.buyer || trade.seller || undefined,
      traderGroup: trade.currency ? "market-data" : undefined,
      tradeType: sideInfo.aggressor === "unknown" ? "unknown" : "taker",
    };
  });

  const ownTrades: OwnTrade[] = trades
    .filter((trade) => trade.traderId && trade.traderId !== "XIRECS")
    .map((trade) => ({
      ...trade,
      id: `${trade.id}-own`,
      traderGroup: "internal",
      tradeType: "maker",
      strategyTag: "uploaded-own-trade",
    }));

  return {
    product: {
      id: productId,
      symbol: productId,
      displayName: productId,
      tickSize: 1,
    },
    bookSnapshots: buildSnapshots(sortedRows),
    trades,
    ownTrades,
    pnlSeries: buildPnlSeries(sortedRows),
    positionSeries: buildPositionSeries(sortedRows),
    indicators: buildIndicators(sortedRows),
    logs: buildLogs(productId, sortedRows),
  };
}

export async function loadTutorialDatasets(): Promise<MarketDataset[]> {
  return Promise.all(
    tutorialDatasetConfigs.map(async (config) => {
      const [pricesResponse, tradesResponse] = await Promise.all([
        fetch(config.pricesPath),
        fetch(config.tradesPath),
      ]);

      if (!pricesResponse.ok || !tradesResponse.ok) {
        throw new Error(`Failed to load tutorial files for ${config.name}.`);
      }

      const [pricesText, tradesText] = await Promise.all([
        pricesResponse.text(),
        tradesResponse.text(),
      ]);
      const priceRows = parsePriceRows(pricesText);
      const tradeRows = parseTradeRows(tradesText);

      const productIds = [...new Set(priceRows.map((row) => row.product))];
      const products = productIds.map((productId) =>
        createProductData(
          productId,
          priceRows.filter((row) => row.product === productId),
          tradeRows.filter((row) => row.symbol === productId)
        )
      );

      return {
        id: config.id,
        name: config.name,
        description: config.description,
        source: config.source,
        createdAt: new Date().toISOString(),
        products,
        metadata: {
          round: config.round,
          day: config.day,
          priceSource: config.pricesPath,
          tradeSource: config.tradesPath,
          rowCount: priceRows.length,
          snapshotCount: priceRows.length,
          tradeCount: tradeRows.length,
          ownTradeCount: products.reduce(
            (sum, product) => sum + product.ownTrades.length,
            0
          ),
        },
      };
    })
  );
}
