/** EAS line icons: 24px grid, 1.75 stroke, round caps. One visual family for
 * navigation, request categories and inline status; decorative by default. */
const PATHS = {
  calendar: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>,
  people: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20v-1a5 5 0 0 1 5-5h3a5 5 0 0 1 5 5v1M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20v-1a5 5 0 0 0-3.5-4.8" /></>,
  card: <><rect x="2.5" y="5" width="19" height="14" rx="2" /><path d="M2.5 10h19M6.5 15h4" /></>,
  chart: <><path d="M4 20V4M4 20h16" /><path d="M8 16v-4M12 16V8M16 16v-6" /></>,
  box: <><path d="m12 3 8.5 4.5v9L12 21l-8.5-4.5v-9Z" /><path d="m3.5 7.5 8.5 4.5 8.5-4.5M12 12v9" /></>,
  building: <><rect x="4" y="3" width="11" height="18" rx="1.5" /><path d="M15 9h4.5a.5.5 0 0 1 .5.5V21M8 7h3M8 11h3M8 15h3M3 21h18" /></>,
  shield: <><path d="M12 21s7.5-3.5 7.5-9.5V5.5L12 3 4.5 5.5v6c0 6 7.5 9.5 7.5 9.5Z" /></>,
  lock: <><rect x="4.5" y="10.5" width="15" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></>,
  server: <><rect x="3" y="4" width="18" height="7" rx="1.5" /><rect x="3" y="13" width="18" height="7" rx="1.5" /><path d="M7 7.5h.01M7 16.5h.01" /></>,
  scale: <><path d="M12 3v18M7 21h10M5 7h14" /><path d="m5 7-3 7a3 3 0 0 0 6 0ZM19 7l-3 7a3 3 0 0 0 6 0Z" /></>,
  trend: <><path d="m3 17 6-6 4 4 8-8" /><path d="M15 7h6v6" /></>,
  file: <><path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8Z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>,
  layers: <><path d="m12 3-9 4.5 9 4.5 9-4.5Z" /><path d="m3 12 9 4.5 9-4.5M3 16.5 12 21l9-4.5" /></>,
  alert: <><path d="M10.3 4.2 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" /><path d="M12 9.5v4M12 17h.01" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="2.75" /></>,
  download: <><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M4.5 19.5h15" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.4-4.4" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  user: <><circle cx="12" cy="8" r="3.75" /><path d="M4.5 20v-.5A5.5 5.5 0 0 1 10 14h4a5.5 5.5 0 0 1 5.5 5.5v.5" /></>,
  expand: <><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></>,
  bolt: <><path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12Z" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></>,
  spark: <><path d="M12 3.5 13.8 9 19.5 10.5 13.8 12 12 17.5 10.2 12 4.5 10.5 10.2 9Z" /><path d="M18.5 16.5 19.2 18.3 21 19l-1.8.7-.7 1.8-.7-1.8L16 19l1.8-.7Z" /></>,
  edit: <><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16Z" /><path d="m13.5 6.5 4 4" /></>,
  folder: <><path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h4l2 2.5h8A1.5 1.5 0 0 1 20.5 10v8A1.5 1.5 0 0 1 19 19.5H5A1.5 1.5 0 0 1 3.5 18Z" /></>,
  block: <><circle cx="12" cy="12" r="8.5" /><path d="m6 6 12 12" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2.5v3M12 18.5v3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M2.5 12h3M18.5 12h3M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1" /></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8.5 7V5.5A1.5 1.5 0 0 1 10 4h4a1.5 1.5 0 0 1 1.5 1.5V7M3 12.5h18" /></>,
  megaphone: <><path d="M3.5 10v4h3l7 4.5v-13L6.5 10Z" /><path d="M17 9a4 4 0 0 1 0 6" /></>,
  plug: <><path d="M9 3v5M15 3v5M6.5 8h11v3a5.5 5.5 0 0 1-11 0ZM12 16.5V21" /></>,
  copy: <><rect x="8.5" y="8.5" width="12" height="12" rx="2" /><path d="M15.5 8.5V5A1.5 1.5 0 0 0 14 3.5H5A1.5 1.5 0 0 0 3.5 5v9A1.5 1.5 0 0 0 5 15.5h3.5" /></>,
  check: <><path d="m5 12.5 4.5 4.5L19 7.5" /></>,
  x: <><path d="M6 6l12 12M18 6 6 18" /></>,
  arrow: <><path d="M4 12h16M14 6l6 6-6 6" /></>,
  chevron: <><path d="m6 9 6 6 6-6" /></>,
  hourglass: <><path d="M6.5 3h11M6.5 21h11M7.5 3c0 4.5 4.5 6.5 4.5 9s-4.5 4.5-4.5 9M16.5 3c0 4.5-4.5 6.5-4.5 9s4.5 4.5 4.5 9" /></>,
  reset: <><path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5" /><path d="M4 4v4.5h4.5" /></>,
};

export default function Icon({ name, size = 18, label, className = "" }) {
  const glyph = PATHS[name] || PATHS.file;
  return (
    <svg
      className={`eas-icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : "true"}
      focusable="false"
    >
      {glyph}
    </svg>
  );
}
