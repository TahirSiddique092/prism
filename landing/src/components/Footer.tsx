import Logo from "./Logo";

const REPO = "https://github.com/TahirSiddique092/prism";

export default function Footer() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-4">
          {/* Brand info */}
          <div className="md:col-span-1">
            <a href="#top" aria-label="PRISM home">
              <Logo size={24} />
            </a>
            <p className="mt-4 text-sm leading-relaxed text-muted">
              Personal Relational Intelligent Search Machine
            </p>
          </div>

          {/* Column 1: Navigation / Sections */}
          <div>
            <h4 className="overline text-xs font-semibold text-ink">Navigation</h4>
            <ul className="mt-4 space-y-2.5 text-sm text-muted">
              <li>
                <a
                  href="#features"
                  className="transition-colors hover:text-ink hover:underline hover:underline-offset-4 decoration-1"
                >
                  Features & Capabilities
                </a>
              </li>
              <li>
                <a
                  href="#architecture"
                  className="transition-colors hover:text-ink hover:underline hover:underline-offset-4 decoration-1"
                >
                  Polyglot Architecture
                </a>
              </li>
              <li>
                <a
                  href="#run"
                  className="transition-colors hover:text-ink hover:underline hover:underline-offset-4 decoration-1"
                >
                  Quickstart & Run
                </a>
              </li>
              <li>
                <a
                  href="#top"
                  className="transition-colors hover:text-ink hover:underline hover:underline-offset-4 decoration-1"
                >
                  Back to Top ↑
                </a>
              </li>
            </ul>
          </div>

          {/* Column 2: Five Datastores */}
          <div>
            <h4 className="overline text-xs font-semibold text-ink">Datastores</h4>
            <ul className="mt-4 space-y-2 text-sm text-muted">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#e8902a]" />
                <span className="text-ink-soft">MySQL</span>
                <span className="mono text-[0.75rem] text-faint">FULLTEXT</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#2f6df0]" />
                <span className="text-ink-soft">pgvector</span>
                <span className="mono text-[0.75rem] text-faint">Embeddings</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#16a34a]" />
                <span className="text-ink-soft">Neo4j</span>
                <span className="mono text-[0.75rem] text-faint">Topic Graph</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#e11d48]" />
                <span className="text-ink-soft">Redis</span>
                <span className="mono text-[0.75rem] text-faint">Query Cache</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#a855f7]" />
                <span className="text-ink-soft">MinIO</span>
                <span className="mono text-[0.75rem] text-faint">PDF Storage</span>
              </li>
            </ul>
          </div>

          {/* Column 3: Stack & Repository */}
          <div>
            <h4 className="overline text-xs font-semibold text-ink">Project</h4>
            <ul className="mt-4 space-y-2.5 text-sm text-muted">
              <li>
                <a
                  href={REPO}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex items-center gap-1.5 font-medium text-ink hover:underline hover:underline-offset-4 decoration-1"
                >
                  GitHub Repository ↗
                </a>
              </li>
              <li className="text-xs text-muted">
                <span className="mono text-faint">Stack:</span> Next.js + Flask API
              </li>
              <li className="text-xs text-muted">
                <span className="mono text-faint">Model:</span> all-MiniLM-L6-v2
              </li>
              <li className="text-xs text-muted">
                <span className="mono text-faint">Command:</span> docker compose up
              </li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}
