const REPO = "https://github.com/TahirSiddique092/prism";

const SPECTRUM = [
  { c: "#e11d48", y2: 104 },
  { c: "#f59e0b", y2: 128 },
  { c: "#eab308", y2: 150 },
  { c: "#16a34a", y2: 172 },
  { c: "#06b6d4", y2: 194 },
  { c: "#6366f1", y2: 216 },
  { c: "#a855f7", y2: 240 },
];

function PrismGraphic() {
  return (
    <svg viewBox="0 0 520 320" fill="none" className="w-full max-w-[520px]" aria-hidden="true">
      <defs>
        <linearGradient id="face" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="1" stopColor="#efece4" stopOpacity="0.5" />
        </linearGradient>
        <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="4" />
        </filter>
      </defs>

      {/* incoming beam */}
      <line x1="8" y1="172" x2="214" y2="172" stroke="#c9c3b6" strokeWidth="1.6" />
      <line x1="8" y1="172" x2="214" y2="172" stroke="#17161b" strokeWidth="1.6" className="beam" />
      <circle cx="8" cy="172" r="3" fill="#17161b" />

      {/* refracted spectrum — soft glow + crisp line */}
      <g filter="url(#soft)" opacity="0.5">
        {SPECTRUM.map((r, i) => (
          <line key={`g${i}`} x1="300" y1="186" x2="512" y2={r.y2} stroke={r.c} strokeWidth="3" />
        ))}
      </g>
      {SPECTRUM.map((r, i) => (
        <line key={`c${i}`} x1="300" y1="186" x2="512" y2={r.y2} stroke={r.c} strokeWidth="1.4" />
      ))}

      {/* the prism */}
      <path
        d="M262 72 L360 250 L164 250 Z"
        fill="url(#face)"
        stroke="#17161b"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Hero() {
  return (
    <header id="top" className="relative overflow-hidden">
      {/* faint construction grid, fading out */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          backgroundImage:
            "linear-gradient(#e4dfd4 1px, transparent 1px), linear-gradient(90deg, #e4dfd4 1px, transparent 1px)",
          backgroundSize: "88px 88px",
          maskImage: "radial-gradient(ellipse 70% 55% at 28% 18%, #000 18%, transparent 72%)",
          WebkitMaskImage: "radial-gradient(ellipse 70% 55% at 28% 18%, #000 18%, transparent 72%)",
          opacity: 0.6,
        }}
      />

      <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 pb-20 pt-16 md:pt-24 lg:grid-cols-[1.05fr_0.95fr] lg:pb-28">
        <div>
          <p className="overline rise">Personal · Relational · Intelligent · Search Machine</p>

          <h1 className="rise font-display mt-6 text-[2.7rem] leading-[1.03] tracking-[-0.015em] text-ink sm:text-6xl lg:text-[4.1rem]" style={{ animationDelay: "0.06s" }}>
            Search your documents
            <br />
            <span className="italic" style={{ fontWeight: 400 }}>
              like you&rsquo;d ask a friend.
            </span>
          </h1>

          <div className="rule-spectrum rise mt-7 w-28" style={{ animationDelay: "0.18s" }} />

          <p className="rise mt-7 max-w-xl text-lg leading-relaxed text-ink-soft" style={{ animationDelay: "0.24s" }}>
            PRISM reads your PDFs, understands what they <em className="font-display italic">mean</em>, and
            surfaces the exact passage — then shows you the source. Semantic search, a topic graph, and an
            inline reader, over five databases working as one.
          </p>

          <div className="rise mt-9 flex flex-wrap items-center gap-5" style={{ animationDelay: "0.32s" }}>
            <a
              href={REPO}
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-[0.95rem] font-medium text-paper shadow-[0_10px_30px_-12px_rgba(23,22,27,0.6)] transition-transform hover:-translate-y-0.5"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49l-.01-1.9c-2.78.62-3.37-1.21-3.37-1.21-.46-1.18-1.11-1.5-1.11-1.5-.9-.63.07-.62.07-.62 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.51.34 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.8-4.57 5.06.36.32.68.94.68 1.9l-.01 2.82c0 .27.18.59.69.49A10.02 10.02 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
              </svg>
              View on GitHub
            </a>
            <a href="#run" className="group inline-flex items-center gap-1.5 text-[0.95rem] font-medium text-ink">
              <span className="border-b border-line-2 pb-0.5 transition-colors group-hover:border-ink">Run it locally</span>
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </a>
          </div>

          <p className="mono rise mt-7 text-xs text-faint" style={{ animationDelay: "0.44s" }}>
            open source · no cloud · one command to run
          </p>
        </div>

        <div className="rise flex justify-center lg:justify-end" style={{ animationDelay: "0.1s" }}>
          <PrismGraphic />
        </div>
      </div>
    </header>
  );
}
