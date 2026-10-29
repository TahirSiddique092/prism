"use client";

import { useSyncExternalStore } from "react";
import { formatDate, formatDateTime } from "@/lib/analytics";

// "Are we in the browser?" never changes after load, so nothing to subscribe to.
const subscribe = () => () => {};

interface LocalTimeProps {
  /** UTC timestamp from the API, e.g. "2026-10-29T16:00:09Z". */
  iso: string | null | undefined;
  /** Also show the time of day. */
  withTime?: boolean;
  /** Text shown when there is no timestamp. */
  empty?: string;
}

/**
 * A timestamp shown in the viewer's own time zone (slice-25).
 *
 * Server rendering runs in the container's time zone (UTC), so the date is
 * filled in only by the browser: the server and the hydration pass render "—",
 * then the client renders the local date. This avoids both a wrong date near
 * midnight and a hydration mismatch.
 */
export default function LocalTime({ iso, withTime = false, empty = "—" }: LocalTimeProps) {
  const inBrowser = useSyncExternalStore(subscribe, () => true, () => false);
  if (!iso) return <>{empty}</>;
  const text = inBrowser ? (withTime ? formatDateTime(iso) : formatDate(iso)) : "—";
  return <time dateTime={iso}>{text}</time>;
}
