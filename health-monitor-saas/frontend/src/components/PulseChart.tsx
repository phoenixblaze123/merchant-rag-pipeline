import { useEffect, useMemo, useRef, useState } from "react";
import type { Reading } from "../api";

type Props = {
  readings: Reading[];
  low: number;
  high: number;
  hours: number;
  minQuality?: number;
};

const H = 260;
const M = { top: 16, right: 56, bottom: 28, left: 40 };
const GAP_MS = 5 * 60_000; // break the line where the band wasn't worn

const fmtTime = (d: Date) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Heart rate over time: one series, threshold reference lines, crosshair tooltip. */
export default function PulseChart({ readings, low, high, hours, minQuality = 0.5 }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const points = useMemo(
    () =>
      readings
        .filter((r) => r.signal_quality == null || r.signal_quality >= minQuality)
        .map((r) => ({ ...r, t: new Date(r.recorded_at).getTime() })),
    [readings, minQuality],
  );
  const dropped = readings.length - points.length;

  const end = Date.now();
  const start = end - hours * 3600_000;
  const innerW = width - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const bpms = points.map((p) => p.bpm);
  const yMin = Math.floor(Math.min(low - 10, ...bpms) / 20) * 20;
  const yMax = Math.ceil(Math.max(high + 10, ...bpms) / 20) * 20;

  const x = (t: number) => M.left + ((t - start) / (end - start)) * innerW;
  const y = (v: number) => M.top + (1 - (v - yMin) / (yMax - yMin)) * innerH;

  const path = useMemo(() => {
    let d = "";
    let prev = -Infinity;
    for (const p of points) {
      d += `${p.t - prev > GAP_MS ? "M" : "L"}${x(p.t).toFixed(1)},${y(p.bpm).toFixed(1)}`;
      prev = p.t;
    }
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, width, yMin, yMax, start]);

  const yTicks: number[] = [];
  for (let v = yMin; v <= yMax; v += 20) yTicks.push(v);
  const xTickEvery = hours <= 6 ? 1 : hours <= 24 ? 4 : 24;
  const xTicks: number[] = [];
  const first = new Date(start);
  first.setMinutes(0, 0, 0);
  for (let t = first.getTime() + 3600_000; t < end; t += 3600_000) {
    if (new Date(t).getHours() % xTickEvery === 0) xTicks.push(t);
  }

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    if (!points.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const t = start + ((e.clientX - rect.left) / rect.width) * (end - start);
    let lo = 0;
    let hi = points.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (points[mid].t < t) lo = mid + 1;
      else hi = mid;
    }
    if (lo > 0 && Math.abs(points[lo - 1].t - t) < Math.abs(points[lo].t - t)) lo -= 1;
    setHover(lo);
  };

  const hp = hover != null ? points[hover] : null;
  const last = points[points.length - 1];

  return (
    <div className="chart" ref={wrap}>
      {points.length === 0 ? (
        <div className="chart-empty muted">No pulse data in this window yet. Connect a device to start streaming.</div>
      ) : (
        <svg width={width} height={H} role="img" aria-label={`Heart rate over the last ${hours} hours`}>
          {yTicks.map((v) => (
            <g key={v}>
              <line className="grid" x1={M.left} x2={width - M.right} y1={y(v)} y2={y(v)} />
              <text className="tick" x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end">{v}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} className="tick" x={x(t)} y={H - 8} textAnchor="middle">
              {hours > 24 ? new Date(t).toLocaleDateString([], { weekday: "short" }) : fmtTime(new Date(t))}
            </text>
          ))}

          {[
            { v: high, label: `High ${high}` },
            { v: low, label: `Low ${low}` },
          ].map(({ v, label }) => (
            <g key={label}>
              <line className="threshold" x1={M.left} x2={width - M.right} y1={y(v)} y2={y(v)} />
              <text className="tick" x={width - M.right + 6} y={y(v)} dy="0.32em">{label}</text>
            </g>
          ))}

          <path className="series" d={path} />

          {points
            .filter((p) => p.irregular_rhythm)
            .map((p) => (
              <circle key={p.id} className="flag" cx={x(p.t)} cy={y(p.bpm)} r={5}>
                <title>Irregular rhythm at {fmtTime(new Date(p.t))}</title>
              </circle>
            ))}

          {last && !hp && (
            <text className="end-label" x={Math.min(x(last.t) + 6, width - 4)} y={y(last.bpm) - 10} textAnchor="end">
              {last.bpm} bpm
            </text>
          )}

          {hp && (
            <g pointerEvents="none">
              <line className="crosshair" x1={x(hp.t)} x2={x(hp.t)} y1={M.top} y2={M.top + innerH} />
              <circle className="hover-dot" cx={x(hp.t)} cy={y(hp.bpm)} r={4} />
            </g>
          )}

          <rect
            x={M.left}
            y={M.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
      )}

      {hp && (
        <div
          className="tooltip"
          style={{ left: Math.min(Math.max(x(hp.t), 90), width - 90), top: Math.max(y(hp.bpm) - 72, 0) }}
        >
          <div className="tooltip-time">{new Date(hp.t).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}</div>
          <div><span className="key-line" /> <strong>{hp.bpm}</strong> bpm</div>
          {hp.hrv_ms != null && <div className="muted">HRV {hp.hrv_ms} ms</div>}
          {hp.irregular_rhythm && <div className="status-critical">⚠ Irregular rhythm</div>}
        </div>
      )}

      {dropped > 0 && (
        <p className="footnote muted">
          {dropped} low-signal sample{dropped === 1 ? "" : "s"} hidden (loose band or movement).
        </p>
      )}
    </div>
  );
}
