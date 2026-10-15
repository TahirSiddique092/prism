import Logo from "./Logo";

const REPO = "https://github.com/TahirSiddique092/prism";

export default function Nav() {
  return (
    <nav className="sticky top-0 z-40 border-b border-line bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <a href="#top" aria-label="PRISM home">
          <Logo size={26} />
        </a>
        <div className="flex items-center gap-7">
          <a href="#features" className="hidden text-sm text-muted transition-colors hover:text-ink sm:inline">
            Features
          </a>
          <a href="#architecture" className="hidden text-sm text-muted transition-colors hover:text-ink sm:inline">
            Architecture
          </a>
          <a href="#run" className="hidden text-sm text-muted transition-colors hover:text-ink sm:inline">
            Run&nbsp;it
          </a>
          <a
            href={REPO}
            target="_blank"
            rel="noopener"
            className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper transition-transform hover:-translate-y-0.5"
          >
            GitHub ↗
          </a>
        </div>
      </div>
    </nav>
  );
}
