/** Indian digit grouping: 1234567 -> 12,34,567 */
export function inr(value: number): string {
  return "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value);
}

export function pct(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function label(key: string): string {
  return key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}
