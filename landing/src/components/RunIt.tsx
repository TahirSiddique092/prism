"use client";

import { useState } from "react";
import Reveal from "./Reveal";

const REPO = "https://github.com/TahirSiddique092/prism";
const CMDS = [
  "git clone https://github.com/TahirSiddique092/prism.git",
  "cd prism",
  "docker compose up",
];

const STEPS = [
  { t: "Upload", d: "Your PDF lands in MinIO; text is chunked into MySQL, embedded into pgvector, and its topics written to Neo4j." },
  { t: "Search", d: "Your question is embedded and matched by cosine distance — with FULLTEXT fallback and Redis caching." },
  { t: "Explore", d: "Read the source inline, follow the topic graph to related documents, and review your search analytics." },
];

export default function RunIt() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(CMDS.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <section id="run" className="bg-night text-paper">
      <div className="mx-auto max-w-6xl px-6 py-24 lg:py-32">
        <Reveal>
          <p className="overline" style={{ color: "#8d8a95" }}>03 — Try it</p>
          <h2 className="font-display mt-4 text-4xl leading-[1.08] tracking-[-0.01em] sm:text-5xl">
            No cloud. No keys. <span className="italic">One command.</span>
          </h2>
          <p className="mt-5 max-w-xl text-[#b7b4bf]">
            Everything runs locally in Docker — you need Docker and about 4–6&nbsp;GB of free RAM. The whole stack
            comes up together.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="mt-12 overflow-hidden rounded-2xl border border-[#2a2933] bg-night-2 shadow-[0_40px_90px_-50px_rgba(0,0,0,0.9)]">
            <div className="flex items-center gap-2 border-b border-[#2a2933] px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              <span className="mono ml-3 text-xs text-[#6f6c78]">bash</span>
              <button
                onClick={copy}
                className="mono ml-auto rounded-md border border-[#2f2e3a] px-3 py-1.5 text-xs text-[#b7b4bf] transition-colors hover:border-[#454350] hover:text-paper"
              >
                {copied ? "copied ✓" : "copy"}
              </button>
            </div>
            <div className="p-6 sm:p-7">
              <pre className="mono text-[0.86rem] leading-[1.9] text-[#d7d4df]">
                {CMDS.map((c) => (
                  <div key={c}>
                    <span className="text-[#06b6d4]">$</span> {c}
                  </div>
                ))}
              </pre>
              <div className="rule-spectrum mt-5 w-full opacity-70" />
              <p className="mono mt-5 text-xs text-[#8d8a95]">
                then open <span className="text-paper">http://localhost:3000</span> → register → upload a PDF → search.
              </p>
            </div>
          </div>
        </Reveal>

        <div className="mt-16 grid gap-10 sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.t} delay={i * 0.08}>
              <div className="border-t border-[#2a2933] pt-5">
                <div className="mono text-xs text-[#6f6c78]">{String(i + 1).padStart(2, "0")}</div>
                <h3 className="font-display mt-3 text-xl">{s.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[#9f9ca8]">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-20 flex flex-col items-center text-center">
            <h3 className="font-display max-w-xl text-3xl leading-tight sm:text-4xl">
              Spin up your own searchable library.
            </h3>
            <a
              href={REPO}
              target="_blank"
              rel="noopener"
              className="mt-8 inline-flex items-center gap-2 rounded-full bg-paper px-7 py-3.5 text-[0.95rem] font-medium text-ink transition-all hover:-translate-y-0.5 hover:bg-white shadow-[0_10px_30px_-12px_rgba(0,0,0,0.5)]"
            >
              View the repository ↗
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
