import type {
  BookLevel,
  BookSnapshot,
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
  RawSubmissionLogRow,
  RawSubmissionPositionRow,
  RawSubmissionResultPayload,
  RawSubmissionTradeRow,
  RawTutorialPriceRow,
} from "../../types/rawData";

interface SubmissionPriceRow {
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

interface BundledSubmissionFile {
  path: string;
  contents: string;
}

const bundledLogFiles = import.meta.glob<string>("../../../ROUND1/logs/**/*.log", {
  query: "?raw",
  import: "default",
  eager: true,
});

const bundledJsonFiles = import.meta.glob<string>("../../../ROUND1/logs/**/*.json", {
  query: "?raw",
  import: "default",
  eager: true,
});

function parseNumber(value: string | undefined) {
  if (!value || value.trim() === "") {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseDelimitedCsv(
  text: string,
): Array<Record<string, string | undefined>> {
  const lines = text.trim().split(/\r?\n/);
  const [headerLine, ...rows] = lines;

  if (!headerLine) {
    return [];
  }

  const separator = headerLine.includes(";") ? ";" : ",";
  const headers = headerLine.split(separator).map((column) => column.trim());

  return rows
    .filter((row) => row.trim().length > 0)
    .map((row) => {
      const values = row.split(separator);
      return Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim()]));
    });
}

function parsePriceRows(text: string): SubmissionPriceRow[] {
  const rows = parseDelimitedCsv(text) as unknown as RawTutorialPriceRow[];

  return rows.map((row) => ({
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

function inferTradeSide(price: number, bidPrice?: number, askPrice?: number) {
  if (askPrice !== undefined && price >= askPrice) {
    return { side: "buy" as const, aggressor: "buyer" as const };
  }

  if (bidPrice !== undefined && price <= bidPrice) {
    return { side: "sell" as const, aggressor: "seller" as const };
  }

  return { side: "buy" as const, aggressor: "unknown" as const };
}

function findNearestPriceRow(rows: SubmissionPriceRow[], timestamp: number) {
  return rows.reduce<SubmissionPriceRow | null>((closest, row) => {
    if (!closest) {
      return row;
    }

    return Math.abs(row.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? row : closest;
  }, null);
}

function buildSideLevels(row: SubmissionPriceRow, side: "bid" | "ask"): BookLevel[] {
  return ([1, 2, 3] as const)
    .map((level) => {
      const price = row[`${side}_price_${level}` as keyof SubmissionPriceRow] as number | undefined;
      const quantity = row[`${side}_volume_${level}` as keyof SubmissionPriceRow] as number | undefined;

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

function buildSnapshots(rows: SubmissionPriceRow[]): BookSnapshot[] {
  return rows
    .slice()
    .sort((left, right) => left.timestamp - right.timestamp)
    .map((row) => ({
      timestamp: row.timestamp,
      productId: row.product,
      bids: buildSideLevels(row, "bid"),
      asks: buildSideLevels(row, "ask"),
    }));
}

function buildIndicators(rows: SubmissionPriceRow[]): IndicatorSeries[] {
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

function buildPnlSeries(rows: SubmissionPriceRow[]): PnLPoint[] {
  return rows
    .filter((row) => row.profit_and_loss !== undefined)
    .map((row) => ({
      timestamp: row.timestamp,
      value: row.profit_and_loss!,
    }));
}

function buildPositionSeries(
  rows: SubmissionPriceRow[],
  ownTrades: OwnTrade[],
  finalPosition: number | undefined,
): PositionPoint[] {
  const deltasByTimestamp = new Map<number, number>();

  for (const trade of ownTrades) {
    const delta = trade.side === "buy" ? trade.quantity : -trade.quantity;
    deltasByTimestamp.set(trade.timestamp, (deltasByTimestamp.get(trade.timestamp) ?? 0) + delta);
  }

  const sortedRows = rows.slice().sort((left, right) => left.timestamp - right.timestamp);
  if (sortedRows.length === 0 && finalPosition !== undefined) {
    return [{ timestamp: 0, value: finalPosition }];
  }

  let runningPosition = 0;
  const points: PositionPoint[] = [];

  for (const row of sortedRows) {
    runningPosition += deltasByTimestamp.get(row.timestamp) ?? 0;
    points.push({ timestamp: row.timestamp, value: runningPosition });
  }

  if (points.length > 0 && finalPosition !== undefined) {
    points[points.length - 1] = {
      timestamp: points[points.length - 1].timestamp,
      value: finalPosition,
    };
  }

  return points;
}

function buildLogs(productId: string, entries: RawSubmissionLogRow[] | undefined): LogEntry[] {
  if (!entries?.length) {
    return [];
  }

  return entries
    .flatMap((entry, index) => {
      const messages = [entry.sandboxLog?.trim(), entry.lambdaLog?.trim()].filter(Boolean) as string[];
      return messages.map((message, messageIndex) => ({
        id: `${productId}-submission-log-${entry.timestamp}-${index}-${messageIndex}`,
        timestamp: entry.timestamp,
        productId,
        level: entry.sandboxLog?.trim() ? "warning" as const : "info" as const,
        source: entry.sandboxLog?.trim() ? "submission-sandbox" : "submission-output",
        message,
      }));
    })
    .slice(-14);
}

function buildTrades(
  productId: string,
  productRows: SubmissionPriceRow[],
  tradeRows: RawSubmissionTradeRow[] | undefined,
) {
  const marketTrades: Trade[] = [];
  const ownTrades: OwnTrade[] = [];

  for (const [index, trade] of (tradeRows ?? []).entries()) {
    if (trade.symbol !== productId) {
      continue;
    }

    const referenceRow = findNearestPriceRow(productRows, trade.timestamp);
    const sideInfo =
      trade.buyer === "SUBMISSION"
        ? { side: "buy" as const, aggressor: "buyer" as const }
        : trade.seller === "SUBMISSION"
          ? { side: "sell" as const, aggressor: "seller" as const }
          : inferTradeSide(
              trade.price,
              referenceRow?.bid_price_1,
              referenceRow?.ask_price_1,
            );

    const tradeBase = {
      id: `${productId}-submission-trade-${trade.timestamp}-${index}`,
      timestamp: trade.timestamp,
      productId,
      price: trade.price,
      quantity: trade.quantity,
      side: sideInfo.side,
      aggressor: sideInfo.aggressor,
      buyer: trade.buyer || undefined,
      seller: trade.seller || undefined,
      traderId:
        trade.buyer === "SUBMISSION"
          ? trade.seller || undefined
          : trade.seller === "SUBMISSION"
            ? trade.buyer || undefined
            : trade.buyer || trade.seller || undefined,
      traderGroup: trade.buyer === "SUBMISSION" || trade.seller === "SUBMISSION" ? "submission" : "market",
      tradeType: trade.buyer === "SUBMISSION" || trade.seller === "SUBMISSION"
        ? "maker"
        : sideInfo.aggressor === "unknown"
          ? "maker"
          : "taker",
    } satisfies Trade;

    if (trade.buyer === "SUBMISSION" || trade.seller === "SUBMISSION") {
      ownTrades.push({
        ...tradeBase,
        id: `${tradeBase.id}-own`,
        strategyTag: "submission-log",
      });
    } else {
      marketTrades.push(tradeBase);
    }
  }

  return { marketTrades, ownTrades };
}

function inferRoundFromPath(path: string, payloadRound: string | undefined) {
  if (payloadRound) {
    const parsed = Number(payloadRound);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  const match = path.match(/ROUND(\d+)/i);
  return match ? Number(match[1]) : undefined;
}

function inferDayFromPath(path: string) {
  const match = path.match(/logs\/(-?\d+)\//i);
  return match ? Number(match[1]) : undefined;
}

function buildDatasetName(path: string) {
  const parts = path.replace(/\\/g, "/").split("/");
  const fileName = parts[parts.length - 1] ?? "submission";
  const directoryName = parts[parts.length - 2];
  return directoryName ? `${directoryName} / ${fileName}` : fileName;
}

function parseSubmissionPayload(text: string): RawSubmissionResultPayload {
  return JSON.parse(text) as RawSubmissionResultPayload;
}

function isSubmissionPayload(value: unknown): value is RawSubmissionResultPayload {
  if (!value || typeof value !== "object") {
    return false;
  }

  const payload = value as RawSubmissionResultPayload;
  return typeof payload.activitiesLog === "string" || typeof payload.graphLog === "string";
}

export function normalizeSubmissionPayload(payload: RawSubmissionResultPayload, datasetName: string, sourcePath: string): MarketDataset {
  const priceRows = parsePriceRows(payload.activitiesLog ?? "");
  const productIds = [...new Set(priceRows.map((row) => row.product))];
  const finalPositions = new Map(
    (payload.positions ?? []).map((entry: RawSubmissionPositionRow) => [entry.symbol, entry.quantity]),
  );

  const products: ProductMarketData[] = productIds.map((productId) => {
    const productRows = priceRows.filter((row) => row.product === productId);
    const { marketTrades, ownTrades } = buildTrades(productId, productRows, payload.tradeHistory);

    return {
      product: {
        id: productId,
        symbol: productId,
        displayName: productId,
        tickSize: 1,
      },
      bookSnapshots: buildSnapshots(productRows),
      trades: marketTrades,
      ownTrades,
      pnlSeries: buildPnlSeries(productRows),
      positionSeries: buildPositionSeries(productRows, ownTrades, finalPositions.get(productId)),
      indicators: buildIndicators(productRows),
      logs: buildLogs(productId, payload.logs),
    };
  });

  return {
    id: `submission-${sourcePath}`,
    name: buildDatasetName(datasetName),
    description: "IMC submission log/result import",
    source: "submission",
    createdAt: new Date().toISOString(),
    products,
    metadata: {
      round: inferRoundFromPath(sourcePath, payload.round),
      day: inferDayFromPath(sourcePath),
      submissionId: payload.submissionId,
      resultStatus: payload.status,
      reportedProfit: payload.profit,
      priceSource: sourcePath,
      tradeSource: payload.tradeHistory ? sourcePath : undefined,
      snapshotCount: products.reduce((sum, product) => sum + product.bookSnapshots.length, 0),
      tradeCount: products.reduce((sum, product) => sum + product.trades.length, 0),
      ownTradeCount: products.reduce((sum, product) => sum + product.ownTrades.length, 0),
      logCount: payload.logs?.filter((entry) => entry.lambdaLog?.trim() || entry.sandboxLog?.trim()).length ?? 0,
      rowCount: priceRows.length,
    },
  };
}

export function parseSubmissionResult(text: string, datasetName: string, sourcePath: string): MarketDataset {
  const payload = parseSubmissionPayload(text);
  return normalizeSubmissionPayload(payload, datasetName, sourcePath);
}

export function tryParseSubmissionResult(text: string, datasetName: string, sourcePath: string): MarketDataset | null {
  try {
    const payload = parseSubmissionPayload(text);
    if (!isSubmissionPayload(payload)) {
      return null;
    }
    return normalizeSubmissionPayload(payload, datasetName, sourcePath);
  } catch {
    return null;
  }
}

export async function loadBundledSubmissionDatasets(): Promise<MarketDataset[]> {
  const preferredFiles = new Map<string, BundledSubmissionFile>();

  for (const [path, contents] of Object.entries(bundledJsonFiles)) {
    preferredFiles.set(path.replace(/\.json$/i, ""), { path, contents });
  }

  for (const [path, contents] of Object.entries(bundledLogFiles)) {
    preferredFiles.set(path.replace(/\.log$/i, ""), { path, contents });
  }

  return [...preferredFiles.values()]
    .sort((left, right) => left.path.localeCompare(right.path))
    .map(({ path, contents }) => parseSubmissionResult(contents, path.split("/").pop() ?? path, path));
}
