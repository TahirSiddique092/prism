/** PRISM mark — an equilateral prism refracting a beam into the brand spectrum. */
export default function PrismLogo({ size = 38 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <polygon
        points="20,4 36,36 4,36"
        fill="url(#prismGrad)"
        stroke="#3B82F6"
        strokeWidth="2"
      />
      <line
        x1="20"
        y1="4"
        x2="20"
        y2="36"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1.5"
        strokeDasharray="2 2"
      />
      <line x1="20" y1="20" x2="38" y2="24" stroke="#06B6D4" strokeWidth="2" />
      <line x1="20" y1="20" x2="39" y2="28" stroke="#8B5CF6" strokeWidth="2" />
      <defs>
        <linearGradient
          id="prismGrad"
          x1="20"
          y1="4"
          x2="20"
          y2="36"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#3B82F6" stopOpacity="0.3" />
          <stop offset="1" stopColor="#090D16" stopOpacity="0.8" />
        </linearGradient>
      </defs>
    </svg>
  );
}
