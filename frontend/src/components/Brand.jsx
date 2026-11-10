function Brand({ footer = false, href = "/" }) {
  return (
    <a
      className={`brand ${footer ? "brand-footer" : ""}`}
      href={href}
      aria-label="MannKiDhun home"
    >
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 40 40" fill="none">
          <path
            d="M20 9v17.2a4.7 4.7 0 1 1-2.8-4.3V13l13-3v14.2a4.7 4.7 0 1 1-2.8-4.3V8.6L20 11"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M5.5 15.5a11 11 0 0 0 0 9M9 18a6.3 6.3 0 0 0 0 4"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            opacity=".8"
          />
          <path
            d="M26 34.2q3.2 2.5 6.4 0"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity=".75"
          />
        </svg>
      </span>
      <span className="font-display text-[19px] font-extrabold tracking-[-0.8px]">
        MannKiDhun<span className="text-accent">.</span>
      </span>
    </a>
  );
}

export default Brand;
