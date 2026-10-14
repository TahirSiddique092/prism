import Logo from "./Logo";

const REPO = "https://github.com/TahirSiddique092/prism";

export default function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-14 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Logo size={24} />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Personal Relational Intelligent Search Machine — a DBMS course project.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <a href={REPO} target="_blank" rel="noopener" className="text-sm text-ink hover:underline">
            github.com/TahirSiddique092/prism ↗
          </a>
          <span className="mono text-xs text-faint">clone · docker compose up · localhost:3000</span>
        </div>
      </div>
    </footer>
  );
}
