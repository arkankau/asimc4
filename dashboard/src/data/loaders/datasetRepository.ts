import { mockDataset } from "../mock/mockDataset";
import type { MarketDataset, ProductMarketData } from "../../types/market";
import { loadTutorialDatasets } from "./tutorialDatasetLoader";

export interface DatasetRepository {
  listDatasets(): Promise<MarketDataset[]>;
  getDataset(datasetId: string): Promise<MarketDataset | null>;
  importFile(file: File): Promise<MarketDataset>;
}

function parseCsv(text: string): ProductMarketData[] {
  const lines = text.trim().split(/\r?\n/);
  const [headerLine, ...rows] = lines;

  if (!headerLine) {
    return [];
  }

  const headers = headerLine.split(",").map((column) => column.trim());
  const byProduct = new Map<string, ProductMarketData>();

  for (const row of rows) {
    if (!row.trim()) {
      continue;
    }

    const values = row.split(",").map((value) => value.trim());
    const record = Object.fromEntries(headers.map((header, index) => [header, values[index]]));
    const productId = record.productId;

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
        orderBook: [],
        trades: [],
        indicators: [],
      });
    }

    const product = byProduct.get(productId)!;
    const timestamp = Number(record.timestamp ?? 0);
    const price = Number(record.price ?? 0);
    const quantity = Number(record.quantity ?? 0);

    if (record.kind === "trade") {
      product.trades.push({
        id: record.id ?? `${productId}-${timestamp}-${product.trades.length}`,
        timestamp,
        productId,
        price,
        quantity,
        side: record.side === "buy" ? "buy" : "sell",
        aggressor: record.aggressor === "buyer" ? "buyer" : record.aggressor === "seller" ? "seller" : "unknown",
        traderId: record.traderId || undefined,
        ownTrade: record.ownTrade === "true",
      });
    } else {
      product.orderBook.push({
        timestamp,
        productId,
        side: record.side === "bid" ? "bid" : "ask",
        price,
        quantity,
        level: Number(record.level ?? 1),
      });
    }
  }

  return [...byProduct.values()];
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

  private async ensureTutorialDatasetsLoaded() {
    if (this.tutorialLoaded) {
      return;
    }

    try {
      const tutorialDatasets = await loadTutorialDatasets();

      for (const dataset of tutorialDatasets) {
        this.datasets.set(dataset.id, dataset);
      }
    } catch (error) {
      console.warn("Failed to load tutorial datasets", error);
    } finally {
      this.tutorialLoaded = true;
    }
  }

  async listDatasets() {
    await this.ensureTutorialDatasetsLoaded();
    return [...this.datasets.values()].sort((left, right) => {
      const sourceRank = {
        tutorial: 0,
        upload: 1,
        mock: 2,
      } as const;

      return sourceRank[left.source] - sourceRank[right.source] || left.name.localeCompare(right.name);
    });
  }

  async getDataset(datasetId: string) {
    await this.ensureTutorialDatasetsLoaded();
    return this.datasets.get(datasetId) ?? null;
  }

  async importFile(file: File) {
    const text = await file.text();
    const extension = file.name.split(".").pop()?.toLowerCase();
    const createdAt = new Date().toISOString();

    const dataset =
      extension === "json"
        ? parseJson(text)
        : {
            id: `upload-${createdAt}`,
            name: file.name,
            description: "Imported local dataset",
            source: "upload" as const,
            createdAt,
            products: parseCsv(text),
          };

    this.datasets.set(dataset.id, dataset);
    return dataset;
  }
}

export const datasetRepository: DatasetRepository = new InMemoryDatasetRepository();
