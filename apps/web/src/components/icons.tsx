import * as React from "react";

/**
 * Minimal inline icon set (no icon-library dependency).
 *
 * Every icon is decorative: it is aria-hidden by default and inherits
 * `currentColor`. Icons are sized with CSS classes (e.g. `h-4 w-4`) at the call
 * site, mirroring the rest of the design system.
 */
export type IconProps = React.SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export function CheckCircle2(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.4 2.4 2.4 4.6-5" />
    </Svg>
  );
}

export function Circle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
    </Svg>
  );
}

/** Spinner frame — pair with `animate-spin`. */
export function Loader2(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M21 12a9 9 0 1 1-6.2-8.6" />
      <path d="M21 3v6h-6" />
    </Svg>
  );
}

export function XCircle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </Svg>
  );
}

export function AlertTriangle(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </Svg>
  );
}

export function Info(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-5M12 8h.01" />
    </Svg>
  );
}

export function ArrowRight(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Svg>
  );
}

export function ArrowLeft(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M19 12H5M11 18l-6-6 6-6" />
    </Svg>
  );
}

export function ArrowUpRight(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 17 17 7M8 7h9v9" />
    </Svg>
  );
}

export function Ban(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m5.6 5.6 12.8 12.8" />
    </Svg>
  );
}

export function MinusCircle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12h8" />
    </Svg>
  );
}

export function Download(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3v12M7 10l5 5 5-5" />
      <path d="M5 21h14" />
    </Svg>
  );
}

export function Copy(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M15 5.5A2.5 2.5 0 0 0 12.5 3H6a2 2 0 0 0-2 2v7a2 2 0 0 0 1.5 1.9" />
    </Svg>
  );
}

export function ShieldCheck(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3 5 6v6c0 4 3 7.3 7 9 4-1.7 7-5 7-9V6l-7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </Svg>
  );
}

export function ShieldQuestion(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3 5 6v6c0 4 3 7.3 7 9 4-1.7 7-5 7-9V6l-7-3Z" />
      <path d="M9.8 9.6a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.4v.4" />
      <path d="M12 16.5h.01" />
    </Svg>
  );
}

export function Search(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m20 20-4.6-4.6" />
    </Svg>
  );
}

export function Star(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.9-5.2 2.9 1-5.9L3.5 9.7l5.9-.8L12 3.5Z" />
    </Svg>
  );
}

export function ExternalLink(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 4h6v6M20 4l-8 8" />
      <path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" />
    </Svg>
  );
}

export function Sparkles(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
    </Svg>
  );
}

export function Link2(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 15 15 9" />
      <path d="M11 6.5 12.8 4.7a4 4 0 0 1 5.6 5.6L16.6 12" />
      <path d="M13 17.5 11.2 19.3a4 4 0 0 1-5.6-5.6L7.4 12" />
    </Svg>
  );
}

export function Target(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    </Svg>
  );
}

export function AlignLeft(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6h16M4 12h10M4 18h13" />
    </Svg>
  );
}

export function CheckSquare(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="m8.5 12.2 2.3 2.3 4.7-5" />
    </Svg>
  );
}

export function ListChecks(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6h1.5M9 6h11M4 12h1.5M9 12h11M4 18h1.5M9 18h11" />
      <path d="m3.6 4.8.6.6 1.2-1.4M3.6 10.8l.6.6 1.2-1.4M3.6 16.8l.6.6 1.2-1.4" />
    </Svg>
  );
}

export function MapPin(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </Svg>
  );
}

export function Quote(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 7c-2.5 1-4 3.2-4 6v4h5v-5H7.2c.2-1.6 1-2.8 2.3-3.4L9 7ZM19 7c-2.5 1-4 3.2-4 6v4h5v-5h-2.8c.2-1.6 1-2.8 2.3-3.4L19 7Z" />
    </Svg>
  );
}

export function Wrench(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M15.5 3.5a5 5 0 0 0-6.1 6.6L3.5 16.1a2.1 2.1 0 0 0 3 3l6-5.9a5 5 0 0 0 6.6-6.1l-3 3-2.5-.6-.6-2.5 3-3Z" />
    </Svg>
  );
}

export function FileText(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </Svg>
  );
}

export function FileCheck2(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
      <path d="M14 3v5h5" />
      <path d="m9 14.5 2 2 4-4" />
    </Svg>
  );
}

export function History(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3.2 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
      <path d="M12 8v4.5l3 1.8" />
    </Svg>
  );
}

export function GitCompareArrows(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 4v12a2 2 0 0 0 2 2h1" />
      <path d="m5.5 9.5 2.5 2.5 2.5-2.5" />
      <path d="M19 20V8a2 2 0 0 0-2-2h-1" />
      <path d="m13.5 3.5 2.5 2.5 2.5-2.5" />
    </Svg>
  );
}

export function RefreshCw(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M21 12a9 9 0 0 1-15.5 6.2L3 15.5" />
      <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8.5" />
      <path d="M21 4v5h-5M3 20v-5h5" />
    </Svg>
  );
}

export function Trash2(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 7h16M10 11v6M14 11v6" />
      <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
      <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </Svg>
  );
}

export function Zap(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </Svg>
  );
}

export function CircleSlash2(props: IconProps) {
  return <Ban {...props} />;
}

export function CircleAlert(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V13M12 16.5h.01" />
    </Svg>
  );
}

export function Clock(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V12l3 1.8" />
    </Svg>
  );
}

export function Plus(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function Upload(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 17V5M7 10l5-5 5 5" />
      <path d="M5 21h14" />
    </Svg>
  );
}

export function Settings(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-2.9-1.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a2 2 0 1 1 0-4h.2A1.7 1.7 0 0 0 4.5 8.2l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 4.2V4a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.4 1Z" />
    </Svg>
  );
}

export function FolderOpen(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h3.5l2 2.5H19a2 2 0 0 1 2 2V10" />
      <path d="M3 10h17.2a1.5 1.5 0 0 1 1.4 2l-2 6.2a2 2 0 0 1-1.9 1.4H5a2 2 0 0 1-2-2V10Z" />
    </Svg>
  );
}

export function Boxes(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 3 3 6l6 3 6-3-6-3ZM3 6v6l6 3V9L3 6ZM15 6v6l6 3V9l-6-3Z" />
      <path d="m15 6-6 3v6" />
    </Svg>
  );
}

export function Cpu(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M10 10h4v4h-4zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
    </Svg>
  );
}

export function Plug(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 3v5M15 3v5" />
      <path d="M6 8h12v3a6 6 0 0 1-6 6 6 6 0 0 1-6-6V8Z" />
      <path d="M12 17v4" />
    </Svg>
  );
}

export function TrendingUp(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m3 17 6-6 4 4 8-8" />
      <path d="M15 7h6v6" />
    </Svg>
  );
}

export function PencilRuler(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.4 2.6a2 2 0 0 1 2.8 2.8L12 14.6l-3.4.8.8-3.4Z" />
    </Svg>
  );
}

export function Gauge(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 18a9 9 0 1 1 16 0" />
      <path d="m12 14 3.5-3.5" />
      <circle cx="12" cy="15" r="1.4" fill="currentColor" />
    </Svg>
  );
}
