# ADR 016: Patient calendar grid built from scratch, no library

**Status:** Accepted

## Context

The patient calendar needs a month grid view that displays Events, Incidents, and Diary entries as color-coded pills per day. Several mature React calendar libraries exist (`react-big-calendar`, `@fullcalendar/react`, `react-calendar`, etc.) that could provide a grid out of the box.

The requirements are narrow: a 7×6 month grid, colored pills per day, an inline drawer on click, and a create form for appointments. No drag-and-drop, no recurring events, no time-slot grid.

## Decision

Build the month grid from scratch using Tailwind CSS.

## Consequences

**Good:**
- No additional bundle weight — calendar libraries range from 50 KB to 200 KB gzipped
- No library CSS fighting the existing design system; all styling stays in Tailwind utility classes consistent with the rest of the UI
- No library upgrade surface or breaking-change risk
- The required feature set (grid, pills, drawer, create form) maps directly to ~200 lines of straightforward JSX

**Trade-off:**
- Month arithmetic (first day of month, padding days, week rows) must be written by hand — roughly 20–30 lines of date logic using native `Date` or an already-present date utility
- A future requirement for drag-and-drop rescheduling or a week/time-slot view would need more custom code (or a library migration at that point)
