import Reveal from "./Reveal";

const STORES = [
  { n: "MySQL", r: "documents · chunks · FULLTEXT", c: "#e8902a" },
  { n: "pgvector", r: "embeddings", c: "#2f6df0" },
  { n: "Neo4j", r: "topic graph", c: "#16a34a" },
  { n: "Redis", r: "search cache", c: "#e11d48" },
  { n: "MinIO", r: "PDF storage", c: "#a855f7" },
];

function Node({ label, role }: { label: string; role: string }) {
  return (
    <div className="inline-flex items-baseline gap-3 rounded-full border border-line-2 bg-card px-6 py-3">
      <span className="font-medium text-ink">{label}</span>
      <span className="mono text-xs text-muted">{role}</span>
    </div>
  );
}

function Connector() {
  return (
    <div className="flex flex-col items-center py-2" aria-hidden="true">
      <div className="h-7 w-px bg-line-2" />
      <div className="-mt-1 text-faint">▾</div>
    </div>
  );
}

export default function Architecture() {
  return (
    <section id="architecture" className="border-y border-line bg-paper-2/60">
      <div className="mx-auto max-w-6xl px-6 py-24 lg:py-32">
        <Reveal>
          <p className="overline">02 — Under the hood</p>
          <h2 className="font-display mt-4 max-w-2xl text-4xl leading-[1.08] tracking-[-0.01em] text-ink sm:text-5xl">
            Five datastores, <span className="italic">one</span> search box.
          </h2>
          <p className="mt-5 max-w-xl text-ink-soft">
            A deliberate polyglot-persistence design — each store doing what it is best at, orchestrated by a Flask
            API behind a Next.js interface. It is a DBMS project, after all.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="mt-14 flex flex-col items-center text-center">
            <Node label="Next.js" role="App Router UI" />
            <Connector />
            <Node label="Flask API" role="REST + embedding model" />
            <Connector />

            <div className="grid w-full max-w-4xl grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {STORES.map((s) => (
                <div key={s.n} className="overflow-hidden rounded-xl border border-line bg-card text-left">
                  <div className="h-1 w-full" style={{ background: s.c }} />
                  <div className="p-4">
                    <div className="font-medium text-ink">{s.n}</div>
                    <div className="mono mt-1 text-[0.7rem] leading-snug text-muted">{s.r}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
