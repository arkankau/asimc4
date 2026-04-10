import type { Timestamp } from "../types/market";

export function formatTimestamp(timestamp: Timestamp | null) {
  if (timestamp === null) {
    return "No hover";
  }

  return `${(timestamp / 1000).toFixed(3)}s`;
}

export function formatPrice(price: number | null) {
  if (price === null) {
    return "n/a";
  }

  return price.toFixed(2);
}

export function formatQuantity(quantity: number | null) {
  if (quantity === null) {
    return "n/a";
  }

  return quantity.toFixed(0);
}
