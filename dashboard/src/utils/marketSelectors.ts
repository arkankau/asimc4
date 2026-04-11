import type { DashboardInspectionState, DashboardState } from "../types/dashboard";
import type {
  BookLevel,
  BookSnapshot,
  ChartSeriesBundle,
  ChartViewport,
  IndicatorSeries,
  MarketDataset,
  MarketEvent,
  Product,
  ProductMarketData,
  Timestamp,
  Trade,
  OwnTrade,
  TradeFilterSupport,
} from "../types/market";

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

function tradesToEvents(trades: Trade[], kind: "trade" | "ownTrade"): MarketEvent[] {
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
    traderId: trade.traderId,
    traderGroup: trade.traderGroup,
  }));
}

function eventMatchesFilters(event: MarketEvent, state: DashboardState, support: TradeFilterSupport) {
  const quantityRange = state.filters.quantityRange;

  if (event.kind === "bid") {
    return state.visibility.bids;
  }

  if (event.kind === "ask") {
    return state.visibility.asks;
  }

  if (event.kind === "trade") {
    if (!state.visibility.trades) {
      return false;
    }

    if (
      quantityRange &&
      ((quantityRange[0] !== null && event.quantity < quantityRange[0]) ||
        (quantityRange[1] !== null && event.quantity > quantityRange[1]))
    ) {
      return false;
    }

    if (state.filters.tradeType === "own") {
      return false;
    }

    if (state.filters.tradeType !== "all" && event.tradeType !== state.filters.tradeType) {
      return false;
    }

    if (support.supportsTraderGroups && state.filters.traderGroup && event.traderGroup !== state.filters.traderGroup) {
      return false;
    }

    if (support.supportsTraderIds && state.filters.traderId && event.traderId !== state.filters.traderId) {
      return false;
    }

    return true;
  }

  if (event.kind === "ownTrade") {
    if (!state.visibility.ownTrades) {
      return false;
    }

    if (
      quantityRange &&
      ((quantityRange[0] !== null && event.quantity < quantityRange[0]) ||
        (quantityRange[1] !== null && event.quantity > quantityRange[1]))
    ) {
      return false;
    }

    if (state.filters.tradeType !== "all" && state.filters.tradeType !== "own") {
      return false;
    }

    if (support.supportsTraderGroups && state.filters.traderGroup && event.traderGroup !== state.filters.traderGroup) {
      return false;
    }

    if (support.supportsTraderIds && state.filters.traderId && event.traderId !== state.filters.traderId) {
      return false;
    }

    return true;
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

  return {
    availableTraderIds: listUniqueTraders(trades),
    availableTraderGroups: listUniqueTraderGroups(trades),
    supportsTraderIds: trades.some((trade) => Boolean(trade.traderId)),
    supportsTraderGroups: trades.some((trade) => Boolean(trade.traderGroup)),
    minTradeQuantity: quantities.length ? Math.min(...quantities) : null,
    maxTradeQuantity: quantities.length ? Math.max(...quantities) : null,
  };
}

function buildFilterSummary(state: DashboardState, support: TradeFilterSupport) {
  const summary: string[] = [];

  summary.push(`Trade type: ${state.filters.tradeType}`);

  if (support.supportsTraderGroups && state.filters.traderGroup) {
    summary.push(`Group: ${state.filters.traderGroup}`);
  }

  if (support.supportsTraderIds && state.filters.traderId) {
    summary.push(`Trader: ${state.filters.traderId}`);
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

  const bookBidEvents = flattenSnapshotLevels(product.bookSnapshots, "bids", "bid");
  const bookAskEvents = flattenSnapshotLevels(product.bookSnapshots, "asks", "ask");
  const tradeEvents = tradesToEvents(product.trades, "trade");
  const ownTradeEvents = tradesToEvents(product.ownTrades, "ownTrade");
  const filterSupport = getTradeFilterSupport(product);

  const allEvents = [...bookBidEvents, ...bookAskEvents, ...tradeEvents, ...ownTradeEvents]
    .filter((event) => eventMatchesFilters(event, state, filterSupport))
    .filter((event) => eventMatchesDepth(event, state));

  const visibleIndicators = product.indicators.filter(
    (series) => series.id === "mid-price" || state.overlays.enabledIndicators.includes(series.id),
  );

  const fullBounds = collectChartBounds(allEvents, visibleIndicators);
  const viewport = state.chartViewport ?? fullBounds;
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
  };
}

export function derivePnlSummary(product: ProductMarketData | null, inspection: DashboardInspectionState) {
  const latest = getLatestPoint(product?.pnlSeries ?? []);
  const hovered = nearestByTimestamp(product?.pnlSeries ?? [], inspection.hoveredTimestamp);

  return {
    latest,
    hovered,
  };
}
