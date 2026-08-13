import { useRef, useState } from 'react';
import { MONTHS_SHORT, fmtDate } from '../../utils/date';

const W = 900, H = 280, PAD_L = 18, PAD_R = 44, PAD_T = 20, PAD_B = 30;
const innerW = W - PAD_L - PAD_R;
const innerH = H - PAD_T - PAD_B;

/**
 * Cumulative points-over-season SVG chart with hover tooltips.
 * stats : season stats object (from seasonStats in ProfilePage)
 * today : Date
 */
export default function PointsChart({ stats, today }) {
  const svgRef = useRef(null);
  const [tip, setTip] = useState(null);

  // Guard a zero-length season (start === end, e.g. a synthesized single-event
  // player season dated today) so xFor never divides by zero → NaN coordinates.
  const spanMs = Math.max(stats.end - stats.start, 1);
  const totalY = Math.max(stats.totalPts, 1);
  const xFor = (d) => PAD_L + ((d - stats.start) / spanMs) * innerW;
  const yFor = (p) => PAD_T + innerH - (p / totalY) * innerH;

  const monthsAx = [];
  let cur = new Date(stats.start);
  while (cur <= stats.end) { monthsAx.push(new Date(cur)); cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1); }

  let cum = 0;
  const pts = [{ x: xFor(stats.start), y: yFor(0), seed: true }];
  stats.evs.forEach((e) => { cum += e.pts; pts.push({ x: xFor(new Date(e.date)), y: yFor(cum), cumPts: cum, event: e }); });

  const todayInSeason = today >= stats.start && today <= stats.end;
  const todayX = todayInSeason ? xFor(today) : null;
  const pastPts = pts.filter((p) => (p.event ? new Date(p.event.date) <= today : true));
  const futurePts = pts.filter((p) => p.event && new Date(p.event.date) > today);
  let lastPastCum = 0; pastPts.forEach((p) => { if (p.cumPts != null) lastPastCum = p.cumPts; });
  let bridgeX = null, bridgeY = null;
  if (todayInSeason && pastPts.length && futurePts.length) { bridgeX = todayX; bridgeY = yFor(lastPastCum); }

  const lineTo = (arr) => arr.map((p, i) => `${i ? 'L' : 'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const pastPath = pastPts.length > 1 ? lineTo(pastPts) + (bridgeX != null ? ` L ${bridgeX} ${bridgeY}` : '') : '';
  const futurePath = futurePts.length
    ? (bridgeX != null ? `M ${bridgeX} ${bridgeY} ` : `M ${pastPts.at(-1).x} ${pastPts.at(-1).y} `) + futurePts.map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
    : '';
  const areaPath = pastPts.length > 1
    ? (pastPath + (bridgeX != null ? '' : ` L ${pastPts.at(-1).x} ${yFor(0)}`) + (bridgeX != null ? ` L ${bridgeX} ${yFor(0)}` : '') + ` L ${pastPts[0].x} ${yFor(0)} Z`)
    : '';

  const showTip = (p) => {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const parent = svg.parentElement.getBoundingClientRect();
    const cx = p.x * (r.width / W) + r.left - parent.left;
    const cy = p.y * (r.height / H) + r.top - parent.top;
    setTip({ left: cx, top: cy - 12, nm: p.event.name, pts: p.event.pts, cum: p.cumPts, date: p.event.date });
  };

  return (
    <>
      <svg ref={svgRef} className="chart-svg" viewBox="0 0 900 280" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(225,84,99,.35)" />
            <stop offset="100%" stopColor="rgba(225,84,99,0)" />
          </linearGradient>
        </defs>
        <g className="chart-grid">
          {[0, 0.25, 0.5, 0.75, 1].map((t) => { const y = PAD_T + innerH * t; return <line key={`h${t}`} x1={PAD_L} x2={W - PAD_R} y1={y} y2={y} />; })}
          {monthsAx.map((m, i) => { const x = xFor(m); return <line key={`v${i}`} x1={x} x2={x} y1={PAD_T} y2={PAD_T + innerH} />; })}
        </g>
        <g className="chart-axis">
          {monthsAx.map((m, i) => ((i % 2 === 0 && xFor(m) < W - PAD_R - 20)
            ? <text key={`t${i}`} x={xFor(m) + 3} y={H - 10}>{MONTHS_SHORT[m.getMonth()]}</text>
            : null))}
          <text x={W - PAD_R + 6} y={yFor(totalY) + 3}>{totalY}</text>
          <text x={W - PAD_R + 6} y={yFor(0)}>0</text>
        </g>
        {areaPath && <path className="chart-area" d={areaPath} />}
        {pastPath && <path className="chart-line-past" d={pastPath} />}
        {futurePath && <path className="chart-line-future" d={futurePath} />}
        {todayInSeason && (
          <>
            <line className="chart-today" x1={todayX} x2={todayX} y1={PAD_T - 4} y2={PAD_T + innerH + 4} />
            <text className="chart-today-label" x={todayX + 4} y={PAD_T + 8}>DNES</text>
          </>
        )}
        {pts.map((p, i) => (p.seed ? null : (
          <circle
            key={i}
            className={`dot ${new Date(p.event.date) <= today ? 'past' : 'future'}`}
            cx={p.x.toFixed(1)}
            cy={p.y.toFixed(1)}
            r="5.5"
            onMouseEnter={() => showTip(p)}
            onMouseLeave={() => setTip(null)}
          />
        )))}
      </svg>
      {tip && (
        <div className="dot-tip show" style={{ left: tip.left, top: tip.top }}>
          {tip.nm} <b>+{tip.pts}</b><br />{fmtDate(tip.date)} · celkem {tip.cum}
        </div>
      )}
    </>
  );
}
