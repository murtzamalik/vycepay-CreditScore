/**
 * Returns a color based on the VyceScore value.
 * Red: < 500, Amber: 500-700, Green: > 700
 */
export function getScoreColor(score: number): string {
  if (score < 500) return '#ef4444';
  if (score <= 700) return '#f59e0b';
  return '#10b981';
}

/**
 * Returns a human-readable label for a score range.
 */
export function getScoreLabel(score: number): string {
  if (score < 500) return 'High Risk';
  if (score <= 700) return 'Medium Risk';
  return 'Low Risk';
}

/**
 * Formats a score as a string with the range context.
 */
export function formatScore(score: number): string {
  return `${score} / 900`;
}

/**
 * Formats an ISO date string into a localized display string.
 */
export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-KE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Formats an ISO date string with time.
 */
export function formatDateTime(isoDate: string): string {
  return new Date(isoDate).toLocaleString('en-KE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Masks a national ID for display: shows first 3 and last 2 characters.
 */
export function maskNationalId(id: string): string {
  if (id.length <= 5) return id;
  return `${id.slice(0, 3)}${'*'.repeat(id.length - 5)}${id.slice(-2)}`;
}

/**
 * Formats a probability (0-1) as a percentage string.
 */
export function formatPercentage(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}
