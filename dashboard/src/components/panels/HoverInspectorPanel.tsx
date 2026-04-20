import { useMemo } from "react";
import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";
import type { BookSnapshot, LogEntry, MarketEvent, Timestamp } from "../../types/market";

interface SnapshotSummary {
  bestBid: { price: number; quantity: number } | null;
  bestAsk: { price: number; quantity: number } | null;
  mid: number | null;
  spread: number | null;
}

function summarizeSnapshot(snapshot: BookSnapshot | null): SnapshotSummary {
  if (!snapshot) {
    return { bestBid: null, bestAsk: null, mid: null, spread: null };
  }

  const bestBid = snapshot.bids[0] ?? null;
  const bestAsk = snapshot.asks[0] ?? null;
  const mid =
    bestBid && bestAsk
      ? (bestBid.price + bestAsk.price) / 2
      : bestBid?.price ?? bestAsk?.price ?? null;

  return {
    bestBid: bestBid ? { price: bestBid.price, quantity: bestBid.quantity } : null,
    bestAsk: bestAsk ? { price: bestAsk.price, quantity: bestAsk.quantity } : null,
    mid,
    spread: bestBid && bestAsk ? bestAsk.price - bestBid.price : null,
  };
}

function nearestSortedTimestamp(sorted: number[], target: Timestamp): Timestamp | null {
  if (sorted.length === 0) {
    return null;
  }

  let lo = 0;
  let hi = sorted.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < target) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }

  const candidate = sorted[lo];
  if (lo === 0) {
    return candidate;
  }

  const previous = sorted[lo - 1];
  return Math.abs(candidate - target) < Math.abs(previous - target) ? candidate : previous;
}

function renderTradeKindLabel(kind: MarketEvent["kind"]) {
  return kind === "ownTrade" ? "OWN" : "MKT";
}

export function HoverInspectorPanel() {
  const { state, selectedProduct, chartSeries, inspection } = useDashboard();
  const hoveredTimestamp = inspection.hoveredTimestamp;

  const productLookups = useMemo(() => {
    if (!selectedProduct) {
      return null;
    }

    const snapshotByTimestamp = new Map<number, BookSnapshot>();
    for (const snapshot of selectedProduct.bookSnapshots) {
      snapshotByTimestamp.set(snapshot.timestamp, snapshot);
    }

    const positionByTimestamp = new Map<number, number>();
    for (const point of selectedProduct.positionSeries) {
      positionByTimestamp.set(point.timestamp, point.value);
    }

    const logsByTimestamp = new Map<number, LogEntry[]>();
    for (const log of selectedProduct.logs) {
      const bucket = logsByTimestamp.get(log.timestamp) ?? [];
      bucket.push(log);
      logsByTimestamp.set(log.timestamp, bucket);
    }

    return {
      snapshotByTimestamp,
      positionByTimestamp,
      logsByTimestamp,
      snapshotTimestamps: [...snapshotByTimestamp.keys()].sort((left, right) => left - right),
      positionTimestamps: [...positionByTimestamp.keys()].sort((left, right) => left - right),
    };
  }, [selectedProduct]);

  const hoveredSnapshot = useMemo(() => {
    if (!productLookups || hoveredTimestamp === null) {
      return null;
    }

    const exact = productLookups.snapshotByTimestamp.get(hoveredTimestamp);
    if (exact) {
      return exact;
    }

    const nearest = nearestSortedTimestamp(productLookups.snapshotTimestamps, hoveredTimestamp);
    return nearest !== null ? productLookups.snapshotByTimestamp.get(nearest) ?? null : null;
  }, [productLookups, hoveredTimestamp]);

  const snapshotSummary = useMemo(() => summarizeSnapshot(hoveredSnapshot), [hoveredSnapshot]);

  const hoveredPosition = useMemo(() => {
    if (!productLookups || hoveredTimestamp === null) {
      return null;
    }

    if (productLookups.positionByTimestamp.has(hoveredTimestamp)) {
      return {
        timestamp: hoveredTimestamp,
        value: productLookups.positionByTimestamp.get(hoveredTimestamp) ?? 0,
      };
    }

    const nearest = nearestSortedTimestamp(productLookups.positionTimestamps, hoveredTimestamp);
    if (nearest === null) {
      return null;
    }

    return {
      timestamp: nearest,
      value: productLookups.positionByTimestamp.get(nearest) ?? 0,
    };
  }, [productLookups, hoveredTimestamp]);

  const logsAtTimestamp = useMemo(() => {
    if (!productLookups || hoveredTimestamp === null) {
      return [] as LogEntry[];
    }

    return productLookups.logsByTimestamp.get(hoveredTimestamp) ?? [];
  }, [productLookups, hoveredTimestamp]);

  const normalizationReference = useMemo(() => {
    if (
      state.overlays.normalizationMode !== "indicator" ||
      hoveredTimestamp === null ||
      chartSeries.visibleIndicators.length === 0
    ) {
      return null;
    }

    const referenceSeries =
      chartSeries.visibleIndicators.find((series) => series.id === "mid-price") ??
      chartSeries.visibleIndicators[0];

    if (!referenceSeries || referenceSeries.points.length === 0) {
      return null;
    }

    const nearest = referenceSeries.points.reduce<{ timestamp: number; value: number } | null>(
      (closest, point) => {
        if (!closest) {
          return point;
        }

        return Math.abs(point.timestamp - hoveredTimestamp) <
          Math.abs(closest.timestamp - hoveredTimestamp)
          ? point
          : closest;
      },
      null,
    );

    return nearest
      ? { label: referenceSeries.label, value: nearest.value, timestamp: nearest.timestamp }
      : null;
  }, [chartSeries.visibleIndicators, hoveredTimestamp, state.overlays.normalizationMode]);

  const hoveredTrades = useMemo(
    () => [
      ...inspection.visibleOwnTradesAtHoveredTimestamp,
      ...inspection.visibleTradesAtHoveredTimestamp,
    ],
    [
      inspection.visibleOwnTradesAtHoveredTimestamp,
      inspection.visibleTradesAtHoveredTimestamp,
    ],
  );
  const visibleIndicatorSnapshots = useMemo(() => {
    if (hoveredTimestamp === null) {
      return [];
    }

    return chartSeries.visibleIndicators
      .map((series) => {
        if (series.points.length === 0) {
          return null;
        }

        const nearest = series.points.reduce<{ timestamp: number; value: number } | null>((closest, point) => {
          if (!closest) {
            return point;
          }

          return Math.abs(point.timestamp - hoveredTimestamp) < Math.abs(closest.timestamp - hoveredTimestamp)
            ? point
            : closest;
        }, null);

        return nearest
          ? {
              id: series.id,
              label: series.label,
              color: series.color,
              timestamp: nearest.timestamp,
              value: nearest.value,
            }
          : null;
      })
      .filter((series): series is NonNullable<typeof series> => series !== null);
  }, [chartSeries.visibleIndicators, hoveredTimestamp]);

  if (!selectedProduct || hoveredTimestamp === null) {
    return (
      <Panel title="Hover Inspector">
        <p className="hover-inspector__empty">Hover over the chart to inspect market state.</p>
      </Panel>
    );
  }

  const snapshotIsApproximate =
    hoveredSnapshot !== null && hoveredSnapshot.timestamp !== hoveredTimestamp;

  return (
    <Panel
      title="Hover Inspector"
      actions={<span className="chart-card__stat">{selectedProduct.product.displayName}</span>}
    >
      <div className="hover-inspector">
        <section className="hover-inspector__section">
          <header className="hover-inspector__section-header">
            <span className="inspection-label">Timestamp</span>
            <strong>{formatTimestamp(hoveredTimestamp)}</strong>
          </header>
          <div className="hover-inspector__grid">
            <div>
              <span className="inspection-label">Product</span>
              <strong>{selectedProduct.product.displayName}</strong>
            </div>
            <div>
              <span className="inspection-label">Hovered Price</span>
              <strong>{formatPrice(inspection.hoveredPrice)}</strong>
            </div>
            <div>
              <span className="inspection-label">Own Position</span>
              <strong>
                {hoveredPosition ? formatQuantity(hoveredPosition.value) : "--"}
              </strong>
            </div>
            <div>
              <span className="inspection-label">Active Filters</span>
              <strong>
                {inspection.activeFilterSummary.length
                  ? inspection.activeFilterSummary.join(" | ")
                  : "None"}
              </strong>
            </div>
          </div>
        </section>

        <section className="hover-inspector__section">
          <header className="hover-inspector__section-header">
            <span className="inspection-label">Market Snapshot</span>
            {snapshotIsApproximate && hoveredSnapshot ? (
              <span className="hover-inspector__hint">
                nearest @ {formatTimestamp(hoveredSnapshot.timestamp)}
              </span>
            ) : null}
          </header>
          {hoveredSnapshot ? (
            <div className="hover-inspector__grid">
              <div>
                <span className="inspection-label">Best Bid</span>
                <strong>
                  {formatPrice(snapshotSummary.bestBid?.price ?? null)}
                  {" "}x{" "}
                  {formatQuantity(snapshotSummary.bestBid?.quantity ?? null)}
                </strong>
              </div>
              <div>
                <span className="inspection-label">Best Ask</span>
                <strong>
                  {formatPrice(snapshotSummary.bestAsk?.price ?? null)}
                  {" "}x{" "}
                  {formatQuantity(snapshotSummary.bestAsk?.quantity ?? null)}
                </strong>
              </div>
              <div>
                <span className="inspection-label">Mid</span>
                <strong>{formatPrice(snapshotSummary.mid)}</strong>
              </div>
              <div>
                <span className="inspection-label">Spread</span>
                <strong>{formatPrice(snapshotSummary.spread)}</strong>
              </div>
            </div>
          ) : (
            <p className="hover-inspector__empty">No book snapshot available for this product.</p>
          )}
        </section>

        <section className="hover-inspector__section">
          <header className="hover-inspector__section-header">
            <span className="inspection-label">Trades at Timestamp</span>
            <strong>{hoveredTrades.length}</strong>
          </header>
          {hoveredTrades.length === 0 ? (
            <p className="hover-inspector__empty">
              No trades at this timestamp under the current filters.
            </p>
          ) : (
            <div className="hover-inspector__trades">
              {hoveredTrades.map((trade) => (
                <div className="hover-inspector__trade-row" key={`${trade.id}-${trade.kind}`}>
                  <div className="hover-inspector__trade-meta">
                    <span
                      className={`trade-chip trade-chip--${
                        trade.kind === "ownTrade" ? "own" : "market"
                      }`}
                    >
                      {renderTradeKindLabel(trade.kind)}
                    </span>
                    {trade.side ? (
                      <span className={`trade-chip trade-chip--${trade.side}`}>
                        {trade.side.toUpperCase()}
                      </span>
                    ) : null}
                    {trade.traderClass ? (
                      <span className={`trade-chip trade-chip--class-${trade.traderClass}`}>
                        {trade.traderClass}
                      </span>
                    ) : null}
                  </div>
                  <div className="hover-inspector__trade-stats">
                    <span>{formatPrice(trade.price)}</span>
                    <span>x {formatQuantity(trade.quantity)}</span>
                  </div>
                  <div className="hover-inspector__trade-participants">
                    {trade.traderId ? <span>ID {trade.traderId}</span> : null}
                    {trade.traderGroup ? <span>Grp {trade.traderGroup}</span> : null}
                    <span>B {trade.buyer ?? "-"}</span>
                    <span>S {trade.seller ?? "-"}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {normalizationReference || visibleIndicatorSnapshots.length > 0 || logsAtTimestamp.length > 0 ? (
          <section className="hover-inspector__section">
            <header className="hover-inspector__section-header">
              <span className="inspection-label">Indicators & Logs</span>
            </header>
            {normalizationReference ? (
              <div className="hover-inspector__grid">
                <div>
                  <span className="inspection-label">
                    Normalization Ref ({normalizationReference.label})
                  </span>
                  <strong>{formatPrice(normalizationReference.value)}</strong>
                </div>
              </div>
            ) : null}
            {visibleIndicatorSnapshots.length > 0 ? (
              <div className="hover-inspector__grid">
                {visibleIndicatorSnapshots.map((series) => (
                  <div key={series.id}>
                    <span className="inspection-label">{series.label}</span>
                    <strong>{formatPrice(series.value)}</strong>
                  </div>
                ))}
              </div>
            ) : null}
            {logsAtTimestamp.length > 0 ? (
              <div className="hover-inspector__logs">
                {logsAtTimestamp.map((log) => (
                  <div className="hover-inspector__log-row" key={log.id}>
                    <span className="hover-inspector__log-meta">
                      <strong>{log.level.toUpperCase()}</strong>
                      <span>{log.source}</span>
                    </span>
                    <span className="hover-inspector__log-message">{log.message}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </Panel>
  );
}
