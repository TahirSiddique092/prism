type Props = {
  tone?: "ink" | "paper";
  withWordmark?: boolean;
  size?: number;
  className?: string;
};

/** The PRISM mark — a prism refracting a single beam into a spectrum. */
export default function Logo({
  tone = "ink",
  withWordmark = true,
  size = 26,
  className = "",
}: Props) {
  const stroke = tone === "ink" ? "#17161b" : "#f7f5f0";
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M16 6 L26 24 H6 Z"
          fill="none"
          stroke={stroke}
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <line x1="2" y1="16" x2="12" y2="16" stroke={stroke} strokeWidth="1.3" />
        <line x1="20" y1="17" x2="30" y2="11.5" stroke="#e11d48" strokeWidth="1.1" />
        <line x1="20" y1="17.8" x2="30" y2="15" stroke="#eab308" strokeWidth="1.1" />
        <line x1="20" y1="18.6" x2="30" y2="19" stroke="#16a34a" strokeWidth="1.1" />
        <line x1="20" y1="19.4" x2="30" y2="23" stroke="#6366f1" strokeWidth="1.1" />
      </svg>
      {withWordmark && (
        <span
          className="font-sans font-semibold tracking-[0.14em]"
          style={{ color: stroke, fontSize: size * 0.62 }}
        >
          PRISM
        </span>
      )}
    </span>
  );
}
