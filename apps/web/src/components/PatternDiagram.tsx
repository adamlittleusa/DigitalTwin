import { useId, type ReactNode } from "react";
import { PATTERNS, type PatternKey } from "@/patterns";

type Size = "tile" | "page";

type PatternDiagramProps = {
  pattern: PatternKey;
  size: Size;
};

const VIEW_W = 320;
const VIEW_H = 160;
const PAGE_MAX_WIDTH = 640;
const LABEL_SIZE = 11;

const BOX_FILL = "var(--surface-raised)";
const BOX_STROKE = "var(--line-strong)";
const ARROW_STROKE = "var(--text-3)";
const LABEL_FILL = "var(--text-2)";
const ACCENT = "var(--accent)";

const markerId = (scope: string, accent: boolean) =>
  `${scope}-arrow${accent ? "-accent" : ""}`;

type BoxProps = {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  accent?: boolean;
};

function Box({ x, y, w, h, label, accent = false }: BoxProps) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={6}
        fill={BOX_FILL}
        stroke={accent ? ACCENT : BOX_STROKE}
      />
      <Label x={x + w / 2} y={y + h / 2} accent={accent}>
        {label}
      </Label>
    </g>
  );
}

type LabelProps = { x: number; y: number; accent?: boolean; children: string };

function Label({ x, y, accent = false, children }: LabelProps) {
  return (
    <text
      x={x}
      y={y}
      fontFamily="var(--font-mono)"
      fontSize={LABEL_SIZE}
      fill={accent ? ACCENT : LABEL_FILL}
      textAnchor="middle"
      dominantBaseline="central"
    >
      {children}
    </text>
  );
}

type ArrowProps = { d: string; pattern: string; accent?: boolean };

function Arrow({ d, pattern, accent = false }: ArrowProps) {
  return (
    <path
      className="draw"
      d={d}
      fill="none"
      stroke={accent ? ACCENT : ARROW_STROKE}
      strokeWidth={1.5}
      markerEnd={`url(#${markerId(pattern, accent)})`}
      style={{ strokeDasharray: "var(--draw-dash)", strokeDashoffset: 0 }}
    />
  );
}

function Diamond({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  const d = `M ${cx} ${cy - r} L ${cx + r} ${cy} L ${cx} ${cy + r} L ${cx - r} ${cy} Z`;
  return <path d={d} fill={BOX_FILL} stroke={BOX_STROKE} />;
}

function Markers({ pattern }: { pattern: string }) {
  const marker = (accent: boolean) => (
    <marker
      key={String(accent)}
      id={markerId(pattern, accent)}
      viewBox="0 0 8 8"
      refX={7}
      refY={4}
      markerWidth={6}
      markerHeight={6}
      orient="auto-start-reverse"
    >
      <path d="M 0 0 L 8 4 L 0 8 Z" fill={accent ? ACCENT : ARROW_STROKE} />
    </marker>
  );
  return <defs>{[marker(false), marker(true)]}</defs>;
}

const line = (x1: number, y1: number, x2: number, y2: number) =>
  `M ${x1} ${y1} L ${x2} ${y2}`;

function PromptChaining(p: string) {
  return (
    <>
      <Box x={16} y={62} w={64} h={36} label="LLM 1" />
      <Arrow pattern={p} d={line(80, 80, 100, 80)} />
      <Diamond cx={112} cy={80} r={11} />
      <Label x={112} y={112}>
        gate
      </Label>
      <Arrow pattern={p} d={line(124, 80, 144, 80)} />
      <Box x={144} y={62} w={64} h={36} label="LLM 2" />
      <Arrow pattern={p} d={line(208, 80, 240, 80)} />
      <Box x={240} y={62} w={64} h={36} label="LLM 3" />
    </>
  );
}

function Routing(p: string) {
  const rows = [
    { y: 20, label: "A", accent: false },
    { y: 66, label: "B", accent: true },
    { y: 112, label: "C", accent: false },
  ];
  return (
    <>
      <Box x={24} y={62} w={80} h={36} label="Router" />
      {rows.map(({ y, label, accent }) => (
        <g key={label}>
          <Arrow pattern={p} d={line(104, 80, 216, y + 14)} accent={accent} />
          <Box x={216} y={y} w={64} h={28} label={label} accent={accent} />
        </g>
      ))}
    </>
  );
}

function Parallelization(p: string) {
  const ys = [20, 66, 112];
  return (
    <>
      <Box x={8} y={62} w={48} h={36} label="In" />
      {ys.map((y) => (
        <g key={y}>
          <Arrow pattern={p} d={line(56, 80, 136, y + 14)} />
          <Box x={136} y={y} w={48} h={28} label="LLM" />
          <Arrow pattern={p} d={line(184, y + 14, 240, 80)} />
        </g>
      ))}
      <Box x={240} y={62} w={72} h={36} label="Combine" />
    </>
  );
}

function OrchestratorWorkers(p: string) {
  const xs = [32, 128, 224];
  return (
    <>
      <Box x={112} y={6} w={96} h={30} label="Orchestrator" />
      {xs.map((x) => (
        <g key={x}>
          <Arrow pattern={p} d={line(160, 36, x + 32, 64)} />
          <Box x={x} y={64} w={64} h={28} label="Worker" />
          <Arrow pattern={p} d={line(x + 32, 92, 160, 122)} />
        </g>
      ))}
      <Box x={112} y={122} w={96} h={30} label="Synthesize" />
    </>
  );
}

function EvaluatorOptimizer(p: string) {
  const feedback = "M 180 98 L 180 128 L 60 128 L 60 98";
  return (
    <>
      <Box x={16} y={62} w={88} h={36} label="Generator" />
      <Arrow pattern={p} d={line(104, 80, 136, 80)} />
      <Box x={136} y={62} w={88} h={36} label="Evaluator" />
      <Arrow pattern={p} d={feedback} />
      <Label x={120} y={142}>
        feedback
      </Label>
      <Arrow pattern={p} d={line(224, 80, 256, 80)} />
      <Box x={256} y={62} w={48} h={36} label="Out" />
    </>
  );
}

function AutonomousAgent(p: string) {
  const plan = "M 148 62 C 136 26, 184 26, 172 62";
  return (
    <>
      <Box x={8} y={62} w={56} h={36} label="Human" />
      <Arrow pattern={p} d={line(64, 80, 128, 80)} />
      <Label x={96} y={68}>
        task
      </Label>
      <Box x={128} y={62} w={64} h={36} label="LLM" />
      <Arrow pattern={p} d={plan} />
      <Label x={160} y={22}>
        plan
      </Label>
      <Arrow pattern={p} d={line(192, 72, 248, 72)} />
      <Arrow pattern={p} d={line(248, 88, 192, 88)} />
      <Label x={220} y={104}>
        result
      </Label>
      <Box x={248} y={62} w={56} h={36} label="Tools" />
      <Arrow pattern={p} d={line(160, 98, 160, 124)} />
      <Box x={136} y={124} w={48} h={28} label="Done" />
    </>
  );
}

const GEOMETRY: Record<PatternKey, (p: string) => ReactNode> = {
  "prompt-chaining": PromptChaining,
  routing: Routing,
  parallelization: Parallelization,
  "orchestrator-workers": OrchestratorWorkers,
  "evaluator-optimizer": EvaluatorOptimizer,
  "autonomous-agent": AutonomousAgent,
};

export function PatternDiagram({ pattern, size }: PatternDiagramProps) {
  const { name } = PATTERNS[pattern];
  // Marker ids must be unique per instance: the gallery renders six diagrams
  // on one page and a pattern page can repeat one inside the MDX body.
  const scope = `${pattern}-${useId()}`;
  const style =
    size === "page"
      ? { width: "100%", maxWidth: PAGE_MAX_WIDTH, height: "auto" }
      : { width: "100%", height: "auto" };
  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      role="img"
      aria-label={name}
      style={style}
    >
      <Markers pattern={scope} />
      {GEOMETRY[pattern](scope)}
    </svg>
  );
}
