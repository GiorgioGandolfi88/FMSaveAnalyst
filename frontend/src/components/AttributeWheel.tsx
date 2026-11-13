import type { PlayerAttribute } from "../api";
import { SECTION_COLORS } from "../lib/playerFormat";

interface Props {
  sections: [string, PlayerAttribute[]][];
  percentile: number | null;
  label: string | null;
  centre: string;
  size?: number;
}

function wedge(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const p = (r: number, a: number) => `${cx + r * Math.sin(a)} ${cy - r * Math.cos(a)}`;
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return (
    `M ${p(r0, a0)} L ${p(r1, a0)} A ${r1} ${r1} 0 ${large} 1 ${p(r1, a1)} ` +
    `L ${p(r0, a1)} A ${r0} ${r0} 0 ${large} 0 ${p(r0, a0)} Z`
  );
}

/** Radial bars: one wedge per attribute, length = rank in the role group, colour = section. */
export default function AttributeWheel({ sections, percentile, label, centre, size = 150 }: Props) {
  const items = sections.flatMap(([section, attrs]) =>
    attrs.filter((a) => !a.hidden && a.value !== null).map((a) => ({ section, ...a })));
  const c = size / 2;
  const inner = size * 0.17;
  const outer = size * 0.49;
  const step = (2 * Math.PI) / Math.max(items.length, 1);
  const gap = step * 0.12;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img">
      {items.map((a, i) => {
        const a0 = i * step + gap / 2;
        const a1 = (i + 1) * step - gap / 2;
        const r = inner + ((outer - inner) * (a.rank ?? 0)) / 100;
        return (
          <g key={`${a.section}-${a.key}`}>
            <path d={wedge(c, c, inner, outer, a0, a1)} fill="var(--mantine-color-gray-2)" />
            <path d={wedge(c, c, inner, r, a0, a1)} fill={SECTION_COLORS[a.section]}>
              <title>{`${a.key}: ${a.value} (${a.rank ?? "–"})`}</title>
            </path>
          </g>
        );
      })}
      <circle cx={c} cy={c} r={inner - 2} fill="var(--mantine-color-body)" />
      {percentile !== null && (
        <>
          <text x={c} y={c + 1} textAnchor="middle" fontSize={size * 0.085} fontWeight={700}
            fill="currentColor">{centre}</text>
          {label && (
            <text x={c} y={c + size * 0.075} textAnchor="middle" fontSize={size * 0.05}
              fill="var(--mantine-color-dimmed)">vs {label}</text>
          )}
        </>
      )}
    </svg>
  );
}
