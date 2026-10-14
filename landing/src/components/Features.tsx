import Reveal from "./Reveal";

const BIG = [
  {
    k: "Semantic search",
    lead: "Meaning, not keywords.",
    body: "Your query is embedded with all-MiniLM-L6-v2 and matched by cosine distance in pgvector, so PRISM finds the right passage even when it shares not a single word with what you typed.",
  },
  {
    k: "Topic graph",
    lead: "See how your reading connects.",
    body: "Every upload is woven into a Neo4j graph of topics. Open a document and jump straight to the others that are actually about the same ideas.",
  },
];

const ROWS = [
  { k: "FULLTEXT fallback", body: "When nothing is semantically close enough, MySQL FULLTEXT steps in so an exact phrase always finds its home." },
  { k: "Inline PDF reader", body: "Open any result and read the original document right in the browser, topics and related docs alongside." },
  { k: "Search analytics", body: "Your history, your most-surfaced documents, and what you uploaded but never searched." },
  { k: "Redis cache", body: "Ask again and it returns instantly with a “cached” badge — and clears itself when you add new documents." },
];

export default function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-6 py-24 lg:py-32">
      <Reveal>
        <p className="overline">01 — Capabilities</p>
        <h2 className="font-display mt-4 max-w-2xl text-4xl leading-[1.08] tracking-[-0.01em] text-ink sm:text-5xl">
          Everything you need to <span className="italic">interrogate</span> a library.
        </h2>
      </Reveal>

      <div className="mt-16 grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-2">
        {BIG.map((f, i) => (
          <Reveal key={f.k} delay={i * 0.08} className="h-full">
            <div className="group h-full bg-card p-8 transition-colors hover:bg-paper-2 sm:p-10">
              <div className="mono text-xs text-faint">{String(i + 1).padStart(2, "0")}</div>
              <div className="rule-spectrum mt-4 w-8 opacity-80" />
              <h3 className="font-display mt-6 text-2xl text-ink">{f.lead}</h3>
              <p className="mt-2 text-sm font-medium uppercase tracking-wider text-muted">{f.k}</p>
              <p className="mt-4 max-w-md text-ink-soft">{f.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <div className="mt-px grid overflow-hidden rounded-2xl border border-line sm:grid-cols-2">
        {ROWS.map((f, i) => (
          <Reveal key={f.k} delay={i * 0.05}>
            <div
              className={`group flex h-full gap-5 bg-card p-7 transition-colors hover:bg-paper-2 ${
                i % 2 === 0 ? "sm:border-r" : ""
              } ${i < ROWS.length - (ROWS.length % 2 === 0 ? 2 : 1) ? "border-b" : ""} border-line`}
            >
              <div className="mono pt-1 text-xs text-faint">{String(i + 3).padStart(2, "0")}</div>
              <div>
                <h3 className="font-medium text-ink">{f.k}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.body}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
