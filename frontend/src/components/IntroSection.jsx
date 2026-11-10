function IntroSection() {
  return (
    <section id="page-title" className="py-14 text-center" aria-labelledby="intro-title">
      <p className="eyebrow justify-center">
        <span className="eyebrow-dot" />
        A LITTLE MUSIC FOR THE WAY YOU FEEL
      </p>
      <h1
        id="intro-title"
        className="mt-4 font-display text-[clamp(2.2rem,5vw,3.35rem)] font-bold leading-tight tracking-[-0.055em]"
      >
        Your mood has a <span className="text-accent">soundtrack.</span>
      </h1>
      <p className="mx-auto mt-3 max-w-xl text-[15px] leading-7 text-muted">
        Choose your own vibe or request an optional expression estimate, then explore a music suggestion.
      </p>
    </section>
  );
}

export default IntroSection;
