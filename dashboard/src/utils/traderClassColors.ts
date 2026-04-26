import type { TraderClass } from "../types/market";

const TRADER_CLASS_COLORS: Record<TraderClass, string> = {
  M: "#7ad68f",
  S: "#6fb8ff",
  B: "#f39c5a",
  I: "#c48dff",
  F: "#f4c95d",
};

export const TRADER_CLASS_COLOR_ORDER: TraderClass[] = ["M", "S", "B", "I", "F"];

export function getTraderClassColor(traderClass?: TraderClass) {
  if (!traderClass) {
    return "#d7dce5";
  }

  return TRADER_CLASS_COLORS[traderClass];
}
