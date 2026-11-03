const date = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string): string {
  return date.format(new Date(iso));
}
