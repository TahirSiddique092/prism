import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  delay?: number;
  className?: string;
};

/**
 * Content-visible-by-default reveal. The element is always rendered and
 * readable (good for SSR / no-JS / reduced-motion); a subtle fade-up plays on
 * load via pure CSS when the visitor allows motion. See `.rise` in globals.css.
 */
export default function Reveal({ children, delay = 0, className = "" }: Props) {
  return (
    <div
      className={`rise ${className}`}
      style={delay ? { animationDelay: `${delay}s` } : undefined}
    >
      {children}
    </div>
  );
}
