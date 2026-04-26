import type { DashboardInspectionState, DashboardState } from "../types/dashboard";
import type {
  BookLevel,
  BookSnapshot,
  ChartSeriesBundle,
  ChartViewport,
  IndicatorSeries,
  MarketDataset,
  MarketEvent,
  PnLPoint,
  Product,
  ProductMarketData,
  Timestamp,
  Trade,
  OwnTrade,
  TradeFilterSupport,
  TraderClass,
} from "../types/market";

export interface PerformanceSummary {
  finalValue: number | null;
  maxDrawdown: number | null;
  maxDrawdownStartTimestamp: number | null;
  maxDrawdownEndTimestamp: number | null;
  sharpeLike: number | null;
  sortinoLike: number | null;
  profitFactor: number | null;
  positiveStepRate: number | null;
  stepCount: number;
}

export interface TradeTapeRow {
  id: string;
  timestamp: number;
  kind: "market" | "own";
  side: "buy" | "sell";
  price: number;
  quantity: number;
  tradeType: "maker" | "taker" | "unknown";
  buyer?: string;
  seller?: string;
  traderId?: string;
  traderGroup?: string;
  traderClass?: TraderClass;
}

export interface ProductPerformanceRow {
  productId: string;
  displayName: string;
  finalPnl: number | null;
  contributionShare: number | null;
  sharpeLike: number | null;
  sortinoLike: number | null;
  maxDrawdown: number | null;
  positiveStepRate: number | null;
  ownTradeCount: number;
  marketTradeCount: number;
}

export const TRADER_CLASS_ORDER: TraderClass[] = ["M", "S", "B", "I", "F"];

type FilterableTradeLike = {
  kind: string;
  quantity: number;
  traderClass?: TraderClass;
  traderGroup?: string;
  traderId?: string;
};

function nearestByTimestamp<T extends { timestamp: number }>(items: T[], timestamp: Timestamp | null): T | null {
  if (timestamp === null || items.length === 0) {
    return null;
  }

  return items.reduce<T | null>((closest, current) => {
    if (!closest) {
      return current;
    }

    return Math.abs(current.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? current : closest;
  }, null);
}

function flattenSnapshotLevels(
  snapshots: BookSnapshot[],
  side: "bids" | "asks",
  kind: "bid" | "ask",
): MarketEvent[] {
  return snapshots.flatMap((snapshot) =>
    snapshot[side].map((level) => ({
      id: `${snapshot.productId}-${snapshot.timestamp}-${kind}-${level.level}-${level.price}`,
      timestamp: snapshot.timestamp,
      productId: snapshot.productId,
      kind,
      price: level.price,
      quantity: level.quantity,
      level: level.level,
      side: level.side,
      label: `${kind.toUpperCase()} L${level.level}`,
    })),
  );
}

function getSnapshotMidPrice(snapshot: BookSnapshot | null) {
  if (!snapshot) {
    return null;
  }

  const bestBid = snapshot.bids[0]?.price;
  const bestAsk = snapshot.asks[0]?.price;

  if (bestBid !== undefined && bestAsk !== undefined) {
    return (bestBid + bestAsk) / 2;
  }

  if (bestBid !== undefined) {
    return bestBid;
  }

  if (bestAsk !== undefined) {
    return bestAsk;
  }

  return null;
}

function getNearestSnapshotIndex(snapshots: BookSnapshot[], timestamp: number) {
  if (snapshots.length === 0) {
    return null;
  }

  return snapshots.reduce<number>((closestIndex, snapshot, index) => {
    if (index === 0) {
      return index;
    }

    return Math.abs(snapshot.timestamp - timestamp) < Math.abs(snapshots[closestIndex].timestamp - timestamp)
      ? index
      : closestIndex;
  }, 0);
}

function inferExplicitTraderClass(values: Array<string | undefined>): TraderClass | null {
  const aliases: Record<string, TraderClass> = {
    M: "M",
    MAKER: "M",
    S: "S",
    SMALL: "S",
    B: "B",
    BIG: "B",
    I: "I",
    INFORMED: "I",
    F: "F",
    OWN: "F",
    INTERNAL: "F",
    SUBMISSION: "F",
  };

  for (const value of values) {
    if (!value) {
      continue;
    }

    const tokens = value.toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
    for (const token of tokens) {
      const normalized = token.replace(/\d+$/u, "");
      if (aliases[normalized]) {
        return aliases[normalized];
      }
    }
  }

  return null;
}

function getBigTradeThreshold(trades: Trade[]) {
  const sortedQuantities = trades
    .filter((trade) => trade.tradeType === "taker" || trade.tradeType === "unknown")
    .map((trade) => trade.quantity)
    .sort((left, right) => left - right);

  if (sortedQuantities.length === 0) {
    return null;
  }

  const quantileIndex = Math.min(sortedQuantities.length - 1, Math.floor(sortedQuantities.length * 0.75));
  return sortedQuantities[quantileIndex];
}

function isInformedTrade(product: ProductMarketData, trade: Trade, bigTradeThreshold: number | null) {
  if (trade.tradeType !== "taker") {
    return false;
  }

  if (bigTradeThreshold !== null && trade.quantity < bigTradeThreshold) {
    return false;
  }

  const nearestIndex = getNearestSnapshotIndex(product.bookSnapshots, trade.timestamp);
  if (nearestIndex === null) {
    return false;
  }

  const currentSnapshot = product.bookSnapshots[nearestIndex] ?? null;
  const nextSnapshot =
    product.bookSnapshots[Math.min(nearestIndex + 1, product.bookSnapshots.length - 1)] ?? null;
  const currentMid = getSnapshotMidPrice(currentSnapshot);
  const nextMid = getSnapshotMidPrice(nextSnapshot);

  if (currentMid === null || nextMid === null || currentSnapshot?.timestamp === nextSnapshot?.timestamp) {
    return false;
  }

  const spread =
    currentSnapshot?.bids[0] && currentSnapshot.asks[0]
      ? currentSnapshot.asks[0].price - currentSnapshot.bids[0].price
      : product.product.tickSize ?? 1;
  const direction = trade.side === "buy" ? 1 : -1;
  const alignedMove = (nextMid - currentMid) * direction;

  return alignedMove >= Math.max(product.product.tickSize ?? 1, spread * 0.5);
}

function classifyTrade(
  product: ProductMarketData,
  trade: Trade | OwnTrade,
  kind: "trade" | "ownTrade",
  bigTradeThreshold: number | null,
): TraderClass {
  const explicitTraderClass = inferExplicitTraderClass([
    trade.traderClass,
    trade.traderGroup,
    trade.traderId,
    trade.buyer,
    trade.seller,
  ]);

  if (explicitTraderClass) {
    return explicitTraderClass;
  }

  if (kind === "ownTrade") {
    return "F";
  }

  if (trade.tradeType === "maker") {
    return "M";
  }

  if (isInformedTrade(product, trade as Trade, bigTradeThreshold)) {
    return "I";
  }

  if (bigTradeThreshold !== null && trade.quantity >= bigTradeThreshold) {
    return "B";
  }

  return "S";
}

function matchesTradeFilters(item: FilterableTradeLike, state: DashboardState) {
  const quantityRange = state.filters.quantityRange;
  const isOwn = item.kind === "ownTrade" || item.kind === "own";

  if (isOwn && !state.visibility.ownTrades) {
    return false;
  }

  if (!isOwn && !state.visibility.trades) {
    return false;
  }

  if (
    quantityRange &&
    ((quantityRange[0] !== null && item.quantity < quantityRange[0]) ||
      (quantityRange[1] !== null && item.quantity > quantityRange[1]))
  ) {
    return false;
  }

  if (!item.traderClass || !state.filters.selectedTraderClasses.includes(item.traderClass)) {
    return false;
  }

  if (state.filters.selectedTraderGroups.length > 0) {
    if (!item.traderGroup || !state.filters.selectedTraderGroups.includes(item.traderGroup)) {
      return false;
    }
  }

  if (state.filters.selectedTraderIds.length > 0) {
    if (!item.traderId || !state.filters.selectedTraderIds.includes(item.traderId)) {
      return false;
    }
  }

  return true;
}

function tradesToEvents(
  product: ProductMarketData,
  trades: Trade[],
  kind: "trade" | "ownTrade",
  bigTradeThreshold: number | null,
): MarketEvent[] {
  return trades.map((trade) => ({
    id: trade.id,
    timestamp: trade.timestamp,
    productId: trade.productId,
    kind,
    price: trade.price,
    quantity: trade.quantity,
    side: trade.side,
    label: kind === "ownTrade" ? "Own trade" : `${trade.side.toUpperCase()} trade`,
    tradeType: kind === "ownTrade" ? "maker" : trade.tradeType,
    buyer: trade.buyer,
    seller: trade.seller,
    traderId: trade.traderId,
    traderGroup: trade.traderGroup,
    traderClass: classifyTrade(product, trade, kind, bigTradeThreshold),
  }));
}

function eventsAtTimestamp(events: MarketEvent[], timestamp: Timestamp | null) {
  if (timestamp === null) {
    return [] as MarketEvent[];
  }

  return events.filter((event) => event.timestamp === timestamp);
}

function eventMatchesFilters(event: MarketEvent, state: DashboardState, support: TradeFilterSupport) {
  if (event.kind === "bid") {
    return state.visibility.bids;
  }

  if (event.kind === "ask") {
    return state.visibility.asks;
  }

  if (event.kind === "trade") {
    return matchesTradeFilters(event, state);
  }

  if (event.kind === "ownTrade") {
    return matchesTradeFilters(event, state);
  }

  return true;
}

function eventMatchesDepth(event: MarketEvent, state: DashboardState) {
  if (event.kind === "bid" || event.kind === "ask") {
    return event.level ? state.overlays.depthLevels.includes(event.level) : false;
  }

  return true;
}

function filterEventsToViewport(events: MarketEvent[], viewport: ChartViewport) {
  return events.filter(
    (event) =>
      event.timestamp >= viewport.minTimestamp &&
      event.timestamp <= viewport.maxTimestamp &&
      event.price >= viewport.minPrice &&
      event.price <= viewport.maxPrice,
  );
}

function clampViewportToBounds(viewport: ChartViewport, bounds: ChartViewport): ChartViewport {
  const boundsTimeSpan = Math.max(bounds.maxTimestamp - bounds.minTimestamp, 1);
  const boundsPriceSpan = Math.max(bounds.maxPrice - bounds.minPrice, 1);
  const viewportTimeSpan = Math.min(Math.max(viewport.maxTimestamp - viewport.minTimestamp, 1), boundsTimeSpan);
  const viewportPriceSpan = Math.min(Math.max(viewport.maxPrice - viewport.minPrice, 1), boundsPriceSpan);

  let minTimestamp = viewport.minTimestamp;
  let maxTimestamp = viewport.minTimestamp + viewportTimeSpan;
  let minPrice = viewport.minPrice;
  let maxPrice = viewport.minPrice + viewportPriceSpan;

  if (minTimestamp < bounds.minTimestamp) {
    minTimestamp = bounds.minTimestamp;
    maxTimestamp = minTimestamp + viewportTimeSpan;
  }
  if (maxTimestamp > bounds.maxTimestamp) {
    maxTimestamp = bounds.maxTimestamp;
    minTimestamp = maxTimestamp - viewportTimeSpan;
  }

  if (minPrice < bounds.minPrice) {
    minPrice = bounds.minPrice;
    maxPrice = minPrice + viewportPriceSpan;
  }
  if (maxPrice > bounds.maxPrice) {
    maxPrice = bounds.maxPrice;
    minPrice = maxPrice - viewportPriceSpan;
  }

  return {
    minTimestamp,
    maxTimestamp,
    minPrice,
    maxPrice,
  };
}

export function listProducts(dataset: MarketDataset | null): Product[] {
  return dataset?.products.map((entry) => entry.product) ?? [];
}

export function getDatasetProduct(dataset: MarketDataset | null, productId: string | null): ProductMarketData | null {
  if (!dataset || !productId) {
    return null;
  }

  return dataset.products.find((entry) => entry.product.id === productId) ?? null;
}

export function listUniqueTraders(trades: Array<Trade | OwnTrade>) {
  return [...new Set(trades.map((trade) => trade.traderId).filter(Boolean) as string[])];
}

export function listUniqueTraderGroups(trades: Array<Trade | OwnTrade>) {
  return [...new Set(trades.map((trade) => trade.traderGroup).filter(Boolean) as string[])];
}

export function getTradeFilterSupport(product: ProductMarketData | null): TradeFilterSupport {
  const trades = [...(product?.trades ?? []), ...(product?.ownTrades ?? [])];
  const quantities = trades.map((trade) => trade.quantity);
  const bigTradeThreshold = getBigTradeThreshold(product?.trades ?? []);
  const traderClassCounts: Record<TraderClass, number> = { M: 0, S: 0, B: 0, I: 0, F: 0 };
  let usesInferredTraderClasses = false;

  if (product) {
    for (const trade of product.trades) {
      const traderClass = classifyTrade(product, trade, "trade", bigTradeThreshold);
      traderClassCounts[traderClass] += 1;
      if (!inferExplicitTraderClass([trade.traderClass, trade.traderGroup, trade.traderId, trade.buyer, trade.seller])) {
        usesInferredTraderClasses = true;
      }
    }

    for (const trade of product.ownTrades) {
      const traderClass = classifyTrade(product, trade, "ownTrade", bigTradeThreshold);
      traderClassCounts[traderClass] += 1;
      if (!inferExplicitTraderClass([trade.traderClass, trade.traderGroup, trade.traderId, trade.buyer, trade.seller])) {
        usesInferredTraderClasses = true;
      }
    }
  }

  return {
    availableTraderIds: listUniqueTraders(trades),
    availableTraderGroups: listUniqueTraderGroups(trades),
    availableTraderClasses: TRADER_CLASS_ORDER.filter((traderClass) => traderClassCounts[traderClass] > 0),
    traderClassCounts,
    supportsTraderIds: trades.some((trade) => Boolean(trade.traderId)),
    supportsTraderGroups: trades.some((trade) => Boolean(trade.traderGroup)),
    minTradeQuantity: quantities.length ? Math.min(...quantities) : null,
    maxTradeQuantity: quantities.length ? Math.max(...quantities) : null,
    bigTradeThreshold,
    usesInferredTraderClasses,
  };
}

function buildFilterSummary(state: DashboardState, support: TradeFilterSupport) {
  const summary: string[] = [];

  if (state.filters.selectedTraderClasses.length !== TRADER_CLASS_ORDER.length) {
    summary.push(`Classes: ${state.filters.selectedTraderClasses.join(", ") || "none"}`);
  }

  if (support.supportsTraderGroups && state.filters.selectedTraderGroups.length > 0) {
    summary.push(`Groups: ${state.filters.selectedTraderGroups.join(", ")}`);
  }

  if (support.supportsTraderIds && state.filters.selectedTraderIds.length > 0) {
    summary.push(`Traders: ${state.filters.selectedTraderIds.join(", ")}`);
  }

  if (state.filters.quantityRange) {
    const [min, max] = state.filters.quantityRange;
    if (min !== null || max !== null) {
      summary.push(`Qty: ${min ?? 0}-${max ?? "max"}`);
    }
  }

  if (state.overlays.depthLevels.length > 0) {
    summary.push(`Depth: ${state.overlays.depthLevels.map((level) => `L${level}`).join(", ")}`);
  }

  return summary;
}

export function collectChartBounds(events: MarketEvent[], indicators: IndicatorSeries[] = []): ChartViewport {
  const prices = events.map((event) => event.price);
  const timestamps = events.map((event) => event.timestamp);
  const indicatorPrices = indicators.flatMap((series) => series.points.map((point) => point.value));
  const indicatorTimestamps = indicators.flatMap((series) => series.points.map((point) => point.timestamp));

  const allPrices = [...prices, ...indicatorPrices];
  const allTimestamps = [...timestamps, ...indicatorTimestamps];

  if (allPrices.length === 0 || allTimestamps.length === 0) {
    return {
      minTimestamp: 0,
      maxTimestamp: 1,
      minPrice: 0,
      maxPrice: 1,
    };
  }

  return {
    minTimestamp: Math.min(...allTimestamps),
    maxTimestamp: Math.max(...allTimestamps),
    minPrice: Math.min(...allPrices),
    maxPrice: Math.max(...allPrices),
  };
}

export function buildChartSeriesBundle(product: ProductMarketData | null, state: DashboardState): ChartSeriesBundle {
  if (!product) {
    const emptyViewport = collectChartBounds([]);
    return {
      visibleBids: [],
      visibleAsks: [],
      visibleTrades: [],
      visibleOwnTrades: [],
      visibleEvents: [],
      visibleIndicators: [],
      fullBounds: emptyViewport,
      viewport: emptyViewport,
      filterSummary: [],
    };
  }

  const filterSupport = getTradeFilterSupport(product);
  const bigTradeThreshold = filterSupport.bigTradeThreshold;
  const bookBidEvents = flattenSnapshotLevels(product.bookSnapshots, "bids", "bid");
  const bookAskEvents = flattenSnapshotLevels(product.bookSnapshots, "asks", "ask");
  const tradeEvents = tradesToEvents(product, product.trades, "trade", bigTradeThreshold);
  const ownTradeEvents = tradesToEvents(product, product.ownTrades, "ownTrade", bigTradeThreshold);

  const allEvents = [...bookBidEvents, ...bookAskEvents, ...tradeEvents, ...ownTradeEvents]
    .filter((event) => eventMatchesFilters(event, state, filterSupport))
    .filter((event) => eventMatchesDepth(event, state));

  const visibleIndicators = product.indicators.filter(
    (series) => series.id === "mid-price" || state.overlays.enabledIndicators.includes(series.id),
  );

  const fullBounds = collectChartBounds(allEvents, visibleIndicators);
  const viewport = state.chartViewport ? clampViewportToBounds(state.chartViewport, fullBounds) : fullBounds;
  const visibleEvents = filterEventsToViewport(allEvents, viewport).sort((left, right) => left.timestamp - right.timestamp);
  return {
    visibleBids: visibleEvents.filter((event) => event.kind === "bid"),
    visibleAsks: visibleEvents.filter((event) => event.kind === "ask"),
    visibleTrades: visibleEvents.filter((event) => event.kind === "trade"),
    visibleOwnTrades: visibleEvents.filter((event) => event.kind === "ownTrade"),
    visibleEvents,
    visibleIndicators: visibleIndicators.map((series) => ({
      ...series,
      points: series.points.filter(
        (point) =>
          point.timestamp >= viewport.minTimestamp &&
          point.timestamp <= viewport.maxTimestamp &&
          point.value >= viewport.minPrice &&
          point.value <= viewport.maxPrice,
      ),
    })),
    fullBounds,
    viewport,
    filterSummary: buildFilterSummary(state, filterSupport),
  };
}

export function buildInspectionState(
  product: ProductMarketData | null,
  hoveredEvent: MarketEvent | null,
  visibleSeries: ChartSeriesBundle,
): DashboardInspectionState {
  const hoveredTimestamp = hoveredEvent?.timestamp ?? null;
  const visibleTradesAtHoveredTimestamp = eventsAtTimestamp(visibleSeries.visibleTrades, hoveredTimestamp);
  const visibleOwnTradesAtHoveredTimestamp = eventsAtTimestamp(visibleSeries.visibleOwnTrades, hoveredTimestamp);

  return {
    hoveredTimestamp,
    hoveredProductId: product?.product.id ?? null,
    hoveredEvent,
    hoveredEventType: hoveredEvent?.kind ?? null,
    hoveredPrice: hoveredEvent?.price ?? null,
    hoveredQuantity: hoveredEvent?.quantity ?? null,
    nearestVisibleBid: nearestByTimestamp(visibleSeries.visibleBids, hoveredTimestamp),
    nearestVisibleAsk: nearestByTimestamp(visibleSeries.visibleAsks, hoveredTimestamp),
    nearestVisibleTrade: nearestByTimestamp(visibleSeries.visibleTrades, hoveredTimestamp),
    nearestVisibleOwnTrade: nearestByTimestamp(visibleSeries.visibleOwnTrades, hoveredTimestamp),
    visibleTradesAtHoveredTimestamp,
    visibleOwnTradesAtHoveredTimestamp,
    activeFilterSummary: visibleSeries.filterSummary,
  };
}

export function buildTimestampInspectionState(
  product: ProductMarketData | null,
  hoveredTimestamp: Timestamp | null,
  visibleSeries: ChartSeriesBundle,
): DashboardInspectionState {
  const visibleTradesAtHoveredTimestamp = eventsAtTimestamp(visibleSeries.visibleTrades, hoveredTimestamp);
  const visibleOwnTradesAtHoveredTimestamp = eventsAtTimestamp(visibleSeries.visibleOwnTrades, hoveredTimestamp);
  const nearestVisibleTrade = nearestByTimestamp(visibleSeries.visibleTrades, hoveredTimestamp);
  const nearestVisibleOwnTrade = nearestByTimestamp(visibleSeries.visibleOwnTrades, hoveredTimestamp);
  const hoveredEvent =
    visibleOwnTradesAtHoveredTimestamp[0] ??
    visibleTradesAtHoveredTimestamp[0] ??
    nearestVisibleOwnTrade ??
    nearestVisibleTrade ??
    null;

  return {
    hoveredTimestamp,
    hoveredProductId: product?.product.id ?? null,
    hoveredEvent,
    hoveredEventType: hoveredEvent?.kind ?? null,
    hoveredPrice: hoveredEvent?.price ?? null,
    hoveredQuantity: hoveredEvent?.quantity ?? null,
    nearestVisibleBid: nearestByTimestamp(visibleSeries.visibleBids, hoveredTimestamp),
    nearestVisibleAsk: nearestByTimestamp(visibleSeries.visibleAsks, hoveredTimestamp),
    nearestVisibleTrade,
    nearestVisibleOwnTrade,
    visibleTradesAtHoveredTimestamp,
    visibleOwnTradesAtHoveredTimestamp,
    activeFilterSummary: visibleSeries.filterSummary,
  };
}

export function findNearestEventByTimestamp(events: MarketEvent[], timestamp: number) {
  return nearestByTimestamp(events, timestamp);
}

export function findNearestEventByScreenX(
  events: MarketEvent[],
  mouseX: number,
  scaleX: (timestamp: number) => number,
) {
  return events.reduce<MarketEvent | null>((closest, event) => {
    if (!closest) {
      return event;
    }

    return Math.abs(scaleX(event.timestamp) - mouseX) < Math.abs(scaleX(closest.timestamp) - mouseX) ? event : closest;
  }, null);
}

export function getLatestPoint<T extends { timestamp: number }>(points: T[]) {
  return points.length > 0 ? points[points.length - 1] : null;
}

export function aggregateDatasetPnlSeries(dataset: MarketDataset | null): PnLPoint[] {
  if (!dataset) {
    return [];
  }

  const timestamps = [...new Set(dataset.products.flatMap((product) => product.pnlSeries.map((point) => point.timestamp)))].sort(
    (left, right) => left - right,
  );

  if (timestamps.length === 0) {
    return [];
  }

  const lastSeen = new Map<string, number>();

  return timestamps.map((timestamp) => {
    let total = 0;

    for (const product of dataset.products) {
      const point = product.pnlSeries.find((entry) => entry.timestamp === timestamp);
      if (point) {
        lastSeen.set(product.product.id, point.value);
      }

      total += lastSeen.get(product.product.id) ?? 0;
    }

    return { timestamp, value: total };
  });
}

export function computePerformanceSummary(points: PnLPoint[]): PerformanceSummary {
  if (points.length === 0) {
    return {
      finalValue: null,
      maxDrawdown: null,
      maxDrawdownStartTimestamp: null,
      maxDrawdownEndTimestamp: null,
      sharpeLike: null,
      sortinoLike: null,
      profitFactor: null,
      positiveStepRate: null,
      stepCount: 0,
    };
  }

  const increments = points.slice(1).map((point, index) => point.value - points[index].value);
  const finalValue = points[points.length - 1].value;

  let peakValue = points[0].value;
  let peakTimestamp = points[0].timestamp;
  let maxDrawdown = 0;
  let maxDrawdownStartTimestamp = points[0].timestamp;
  let maxDrawdownEndTimestamp = points[0].timestamp;

  for (const point of points) {
    if (point.value > peakValue) {
      peakValue = point.value;
      peakTimestamp = point.timestamp;
    }

    const drawdown = peakValue - point.value;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
      maxDrawdownStartTimestamp = peakTimestamp;
      maxDrawdownEndTimestamp = point.timestamp;
    }
  }

  if (increments.length === 0) {
    return {
      finalValue,
      maxDrawdown,
      maxDrawdownStartTimestamp,
      maxDrawdownEndTimestamp,
      sharpeLike: null,
      sortinoLike: null,
      profitFactor: null,
      positiveStepRate: null,
      stepCount: 0,
    };
  }

  const meanIncrement = increments.reduce((sum, value) => sum + value, 0) / increments.length;
  const variance =
    increments.reduce((sum, value) => sum + (value - meanIncrement) ** 2, 0) / increments.length;
  const standardDeviation = Math.sqrt(variance);
  const negativeIncrements = increments.filter((value) => value < 0);
  const downsideDeviation =
    negativeIncrements.length > 0
      ? Math.sqrt(
          negativeIncrements.reduce((sum, value) => sum + value ** 2, 0) /
            increments.length,
        )
      : 0;
  const grossProfit = increments.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const grossLoss = -increments.filter((value) => value < 0).reduce((sum, value) => sum + value, 0);

  return {
    finalValue,
    maxDrawdown,
    maxDrawdownStartTimestamp,
    maxDrawdownEndTimestamp,
    sharpeLike:
      standardDeviation > 0 ? (meanIncrement / standardDeviation) * Math.sqrt(increments.length) : null,
    sortinoLike:
      downsideDeviation > 0 ? (meanIncrement / downsideDeviation) * Math.sqrt(increments.length) : null,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : null,
    positiveStepRate: increments.filter((value) => value > 0).length / increments.length,
    stepCount: increments.length,
  };
}

export function deriveProductPerformanceRows(dataset: MarketDataset | null): ProductPerformanceRow[] {
  if (!dataset) {
    return [];
  }

  const datasetSeries = aggregateDatasetPnlSeries(dataset);
  const datasetFinal = datasetSeries[datasetSeries.length - 1]?.value ?? null;

  return dataset.products
    .map((product) => {
      const summary = computePerformanceSummary(product.pnlSeries);
      return {
        productId: product.product.id,
        displayName: product.product.displayName,
        finalPnl: summary.finalValue,
        contributionShare:
          summary.finalValue !== null && datasetFinal !== null && datasetFinal !== 0 ? summary.finalValue / datasetFinal : null,
        sharpeLike: summary.sharpeLike,
        sortinoLike: summary.sortinoLike,
        maxDrawdown: summary.maxDrawdown,
        positiveStepRate: summary.positiveStepRate,
        ownTradeCount: product.ownTrades.length,
        marketTradeCount: product.trades.length,
      };
    })
    .sort((left, right) => (right.finalPnl ?? Number.NEGATIVE_INFINITY) - (left.finalPnl ?? Number.NEGATIVE_INFINITY));
}

export function summarizeSnapshot(snapshot: BookSnapshot | null) {
  if (!snapshot) {
    return null;
  }

  const bestBid = snapshot.bids[0] ?? null;
  const bestAsk = snapshot.asks[0] ?? null;
  return {
    bestBid,
    bestAsk,
    spread: bestBid && bestAsk ? bestAsk.price - bestBid.price : null,
  };
}

export function getNearestSnapshot(product: ProductMarketData | null, timestamp: Timestamp | null) {
  return nearestByTimestamp(product?.bookSnapshots ?? [], timestamp);
}

export function derivePositionSummary(product: ProductMarketData | null, inspection: DashboardInspectionState) {
  const latest = getLatestPoint(product?.positionSeries ?? []);
  const hovered = nearestByTimestamp(product?.positionSeries ?? [], inspection.hoveredTimestamp);

  return {
    latest,
    hovered,
    maxAbsPosition:
      product?.positionSeries.length ? Math.max(...product.positionSeries.map((point) => Math.abs(point.value))) : null,
    ownTradeCount: product?.ownTrades.length ?? 0,
    buyCount: product?.ownTrades.filter((trade) => trade.side === "buy").length ?? 0,
    sellCount: product?.ownTrades.filter((trade) => trade.side === "sell").length ?? 0,
  };
}

export function derivePnlSummary(
  product: ProductMarketData | null,
  inspection: DashboardInspectionState,
  dataset?: MarketDataset | null,
) {
  const latest = getLatestPoint(product?.pnlSeries ?? []);
  const hovered = nearestByTimestamp(product?.pnlSeries ?? [], inspection.hoveredTimestamp);
  const datasetSeries = aggregateDatasetPnlSeries(dataset ?? null);
  const datasetLatest = getLatestPoint(datasetSeries);
  const productPerformance = computePerformanceSummary(product?.pnlSeries ?? []);
  const datasetPerformance = computePerformanceSummary(datasetSeries);

  return {
    latest,
    hovered,
    productPerformance,
    datasetLatest,
    datasetPerformance,
    contributionShare:
      latest && datasetLatest && datasetLatest.value !== 0 ? latest.value / datasetLatest.value : null,
  };
}

export function deriveTradeTape(
  product: ProductMarketData | null,
  inspection: DashboardInspectionState,
  state: DashboardState,
  limit = 14,
) {
  if (!product) {
    return {
      rows: [] as TradeTapeRow[],
      highlightedTradeId: null as string | null,
    };
  }

  const filterSupport = getTradeFilterSupport(product);
  const bigTradeThreshold = filterSupport.bigTradeThreshold;

  const rows: TradeTapeRow[] = [
    ...product.ownTrades.map((trade) => ({
      id: trade.id,
      timestamp: trade.timestamp,
      kind: "own" as const,
      side: trade.side,
      price: trade.price,
      quantity: trade.quantity,
      tradeType: trade.tradeType,
      buyer: trade.buyer,
      seller: trade.seller,
      traderId: trade.traderId,
      traderGroup: trade.traderGroup,
      traderClass: classifyTrade(product, trade, "ownTrade", bigTradeThreshold),
    })),
    ...product.trades.map((trade) => ({
      id: trade.id,
      timestamp: trade.timestamp,
      kind: "market" as const,
      side: trade.side,
      price: trade.price,
      quantity: trade.quantity,
      tradeType: trade.tradeType,
      buyer: trade.buyer,
      seller: trade.seller,
      traderId: trade.traderId,
      traderGroup: trade.traderGroup,
      traderClass: classifyTrade(product, trade, "trade", bigTradeThreshold),
    })),
  ];
  const filteredRows = rows.filter((row) => matchesTradeFilters(row, state));

  const sorted = inspection.hoveredTimestamp !== null
    ? filteredRows
        .slice()
        .sort(
          (left, right) =>
            Math.abs(left.timestamp - inspection.hoveredTimestamp!) - Math.abs(right.timestamp - inspection.hoveredTimestamp!) ||
            right.timestamp - left.timestamp,
        )
    : filteredRows.slice().sort((left, right) => right.timestamp - left.timestamp);

  return {
    rows: sorted.slice(0, limit),
    highlightedTradeId:
      inspection.hoveredTimestamp !== null
        ? nearestByTimestamp(filteredRows, inspection.hoveredTimestamp)?.id ?? null
        : filteredRows[0]?.id ?? null,
  };
}
