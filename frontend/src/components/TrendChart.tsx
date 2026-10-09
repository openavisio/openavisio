"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type Point = { date: string; value: number };

export function TrendChart({ data, unit }: { data: Point[]; unit?: string }) {
  if (data.length < 2) return null;
  const sorted = [...data]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((p) => ({
      d: new Date(p.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      v: p.value,
    }));
  return (
    <ResponsiveContainer width="100%" height={140}>
      <LineChart data={sorted} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="d" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => [`${v}${unit ? ` ${unit}` : ""}`, "Value"]} />
        <Line
          type="monotone"
          dataKey="v"
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
