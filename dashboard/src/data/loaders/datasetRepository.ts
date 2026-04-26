import { mockDataset } from "../mock/mockDataset";
import { loadBundledSubmissionDatasets, tryParseSubmissionResult } from "./imcSubmissionLoader";
import { loadTutorialDatasets } from "./tutorialDatasetLoader";
import type {
  BookLevel,
  BookSnapshot,
  IndicatorSeries,
  MarketDataset,
  OwnTrade,
  PnLPoint,
  PositionPoint,
  ProductMarketData,
  Trade,
} from "../../types/market";
import type { RawFlatMarketRow } from "../../types/rawData";

export interface DatasetRepository {
  listDatasets(): Promise<MarketDataset[]>;
  getDataset(datasetId: string): Promise<MarketDataset | null>;
  importFile(file: File): Promise<MarketDataset>;
}

const UPLOADED_DATASETS_STORAGE_KEY = "dashboard.uploadedDatasets.v1";

function readStoredUploadedDatasets(): MarketDataset[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = window.localStorage.getItem(UPLOADED_DATASETS_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter(
      (entry): entry is MarketDataset =>
        Boolean(entry) &&
        typeof entry === "object" &&
        typeof (entry as MarketDataset).id === "string" &&
        Array.isArray((entry as MarketDataset).products),
    );
  } catch {
    return [];
  }
}

function writeStoredUploadedDatasets(datasets: MarketDataset[]) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(UPLOADED_DATASETS_STORAGE_KEY, JSON.stringify(datasets));
  } catch (error) {
    console.warn(
      "Could not persist uploaded datasets to localStorage — keeping them in memory for this session only.",
      error,
    );
  }
}

function parseDelimitedRows(text: string): RawFlatMarketRow[] {
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
      const values = row.split(separator).map((value) => value.trim());
      return Object.fromEntries(headers.map((header, index) => [header, values[index]])) as unknown as RawFlatMarketRow;
    });
}

function numberOrNull(value: string | undefined) {
  if (!value || value.trim() === "") {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildSnapshotMap() {
  return new Map<number, { bids: BookLevel[]; asks: BookLevel[] }>();
}

function normalizeFlatRows(rows: RawFlatMarketRow[], datasetName: string): MarketDataset {
  const byProduct = new Map<string, ProductMarketData>();

  for (const row of rows) {
    const productId = row.productId;

    if (!productId) {
      continue;
    }

    if (!byProduct.has(productId)) {
      byProduct.set(productId, {
        product: {
          id: productId,
          symbol: productId,
          displayName: productId,
        },
        bookSnapshots: [],
        trades: [],
        ownTrades: [],
        pnlSeries: [],
        positionSeries: [],
        indicators: [],
        logs: [],
      });
    }

    const product = byProduct.get(productId)!;
    const timestamp = numberOrNull(row.timestamp) ?? 0;
    const price = numberOrNull(row.price) ?? 0;
    const quantity = numberOrNull(row.quantity) ?? 0;

    if (row.kind === "trade") {
      const tradeBase = {
        id: row.id ?? `${productId}-${timestamp}-${product.trades.length}`,
        timestamp,
        productId,
        price,
        quantity,
        side: row.side === "sell" ? "sell" : "buy",
        aggressor:
          row.aggressor === "buyer" ? "buyer" : row.aggressor === "seller" ? "seller" : "unknown",
        traderId: row.traderId || undefined,
        traderGroup: undefined,
        tradeType: row.aggressor === "unknown" ? "unknown" : "taker",
      } satisfies Trade;

      if (row.ownTrade === "true") {
        product.ownTrades.push({
          ...tradeBase,
          strategyTag: "uploaded-own-trade",
        } satisfies OwnTrade);
      } else {
        product.trades.push(tradeBase);
      }
      continue;
    }

    const level = numberOrNull(row.level) ?? 1;
    const snapshotMap = (product as ProductMarketData & { _snapshotMap?: Map<number, { bids: BookLevel[]; asks: BookLevel[] }> })._snapshotMap ?? buildSnapshotMap();
    (product as ProductMarketData & { _snapshotMap?: Map<number, { bids: BookLevel[]; asks: BookLevel[] }> })._snapshotMap = snapshotMap;

    if (!snapshotMap.has(timestamp)) {
      snapshotMap.set(timestamp, { bids: [], asks: [] });
    }

    const bookLevel: BookLevel = {
      price,
      quantity,
      level,
      side: row.side === "ask" ? "ask" : "bid",
    };

    if (bookLevel.side === "bid") {
      snapshotMap.get(timestamp)!.bids.push(bookLevel);
    } else {
      snapshotMap.get(timestamp)!.asks.push(bookLevel);
    }
  }

  const products = [...byProduct.values()].map((product) => {
    const snapshotMap = (product as ProductMarketData & { _snapshotMap?: Map<number, { bids: BookLevel[]; asks: BookLevel[] }> })._snapshotMap;
    const snapshots: BookSnapshot[] = snapshotMap
      ? [...snapshotMap.entries()]
          .sort((left, right) => left[0] - right[0])
          .map(([timestamp, levels]) => ({
            timestamp,
            productId: product.product.id,
            bids: levels.bids.sort((left, right) => left.level - right.level),
            asks: levels.asks.sort((left, right) => left.level - right.level),
          }))
      : [];

    return {
      product: product.product,
      bookSnapshots: snapshots,
      trades: product.trades,
      ownTrades: product.ownTrades,
      pnlSeries: [] as PnLPoint[],
      positionSeries: [] as PositionPoint[],
      indicators: [
        {
          id: "uploaded-mid-price",
          label: "Uploaded Mid Price",
          color: "#f4c95d",
          points: snapshots
            .filter((snapshot) => snapshot.bids[0] && snapshot.asks[0])
            .map((snapshot) => ({
              timestamp: snapshot.timestamp,
              value: (snapshot.bids[0].price + snapshot.asks[0].price) / 2,
            })),
        },
      ] as IndicatorSeries[],
      logs: [],
    };
  });

  return {
    id: `upload-${new Date().toISOString()}`,
    name: datasetName,
    description: "Imported local dataset",
    source: "upload",
    createdAt: new Date().toISOString(),
    products,
    metadata: {
      snapshotCount: products.reduce((sum, product) => sum + product.bookSnapshots.length, 0),
      tradeCount: products.reduce((sum, product) => sum + product.trades.length, 0),
      ownTradeCount: products.reduce((sum, product) => sum + product.ownTrades.length, 0),
      rowCount: rows.length,
    },
  };
}

function parseJson(text: string): MarketDataset {
  const parsed = JSON.parse(text) as MarketDataset;

  if (!parsed.id || !Array.isArray(parsed.products)) {
    throw new Error("Uploaded JSON does not match the MarketDataset shape.");
  }

  return parsed;
}

class InMemoryDatasetRepository implements DatasetRepository {
  private datasets = new Map<string, MarketDataset>([[mockDataset.id, mockDataset]]);
  private tutorialLoaded = false;
  private uploadedDatasetsLoaded = false;
  private userUploadedIds = new Set<string>();

  private ensureUploadedDatasetsLoaded() {
    if (this.uploadedDatasetsLoaded) {
      return;
    }

    for (const dataset of readStoredUploadedDatasets()) {
      this.datasets.set(dataset.id, dataset);
      this.userUploadedIds.add(dataset.id);
    }

    this.uploadedDatasetsLoaded = true;
  }

  private persistUploadedDatasets() {
    const uploaded = [...this.datasets.values()].filter((dataset) => this.userUploadedIds.has(dataset.id));
    writeStoredUploadedDatasets(uploaded);
  }

  private async ensureTutorialDatasetsLoaded() {
    if (this.tutorialLoaded) {
      return;
    }

    try {
      const tutorialDatasets = await loadTutorialDatasets();
      const bundledSubmissionDatasets = await loadBundledSubmissionDatasets();

      for (const dataset of tutorialDatasets) {
        this.datasets.set(dataset.id, dataset);
      }

      for (const dataset of bundledSubmissionDatasets) {
        this.datasets.set(dataset.id, dataset);
      }
    } catch (error) {
      console.warn("Failed to load tutorial datasets", error);
    } finally {
      this.tutorialLoaded = true;
    }
  }

  async listDatasets() {
    this.ensureUploadedDatasetsLoaded();
    await this.ensureTutorialDatasetsLoaded();
    return [...this.datasets.values()].sort((left, right) => {
      const sourceRank = { submission: 0, historical: 1, tutorial: 2, upload: 3, mock: 4 } as const;
      return sourceRank[left.source] - sourceRank[right.source] || left.name.localeCompare(right.name);
    });
  }

  async getDataset(datasetId: string) {
    this.ensureUploadedDatasetsLoaded();
    await this.ensureTutorialDatasetsLoaded();
    return this.datasets.get(datasetId) ?? null;
  }

  async importFile(file: File) {
    const text = await file.text();
    const extension = file.name.split(".").pop()?.toLowerCase();
    const dataset =
      extension === "log"
        ? tryParseSubmissionResult(text, file.name, file.name)
        : extension === "json"
          ? tryParseSubmissionResult(text, file.name, file.name) ?? parseJson(text)
          : normalizeFlatRows(parseDelimitedRows(text), file.name);

    if (!dataset) {
      throw new Error(`Unsupported submission file: ${file.name}`);
    }

    this.datasets.set(dataset.id, dataset);
    this.userUploadedIds.add(dataset.id);
    this.persistUploadedDatasets();
    return dataset;
  }
}

export const datasetRepository: DatasetRepository = new InMemoryDatasetRepository();
