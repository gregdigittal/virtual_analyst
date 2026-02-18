const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const dateFmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
});

/** Format a date+time string, returning "—" for null/undefined. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "\u2014";
  try {
    return dateTimeFmt.format(new Date(value));
  } catch {
    return "\u2014";
  }
}

/** Format a date-only string, returning "—" for null/undefined. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "\u2014";
  try {
    return dateFmt.format(new Date(value));
  } catch {
    return "\u2014";
  }
}
