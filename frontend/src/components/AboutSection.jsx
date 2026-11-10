import ShieldIcon from "./ShieldIcon.jsx";

function AboutSection({ checkInHref = "#mood-check" }) {
  return (
    <section
      id="about-us"
      className="about-section grid grid-cols-[minmax(0,1fr)_minmax(280px,0.72fr)] items-center gap-[clamp(28px,7vw,88px)] mt-10 p-[clamp(28px,5vw,56px)] max-[760px]:grid-cols-1 max-[760px]:gap-[25px] max-[760px]:mt-7 max-[760px]:px-[22px] max-[760px]:py-[26px]"
      aria-labelledby="about-title"
    >
      <div className="about-copy">
        <p className="section-eyebrow">A LITTLE MORE ABOUT MANNKIDHUN</p>
        <h2
          id="about-title"
          className="mb-0 mt-3 max-w-[550px] font-display text-[clamp(23px,3vw,31px)] font-bold leading-[1.2] tracking-[-1.2px]"
        >
          Music for how you feel, right now.
        </h2>
        <p className="mb-0 mt-[14px] max-w-[580px] text-sm leading-[1.8] text-subtle">
          MannKiDhun helps you explore a song for the moment you’re in. Choose
          a vibe yourself or, if you want, request a brief expression estimate.
          The estimate is only a starting point—you decide what feels right.
        </p>
        <a
          href={checkInHref}
          className="mt-5 inline-flex items-center gap-[9px] text-[13px] font-bold text-[#6c4cdb] no-underline hover:underline hover:underline-offset-4"
        >
          Check in with yourself <span aria-hidden="true">→</span>
        </a>
      </div>
      <div className="about-promise flex items-start gap-[15px] scroll-mt-6 p-[22px]" id="privacy-note">
        <span className="about-promise-icon grid h-10 w-10 shrink-0 place-items-center">
          <ShieldIcon />
        </span>
        <div>
          <h3 className="mb-0 mt-0.5 font-display text-[15px] font-bold">
            Your moment stays yours.
          </h3>
          <p className="mb-0 mt-2 text-xs leading-[1.7] text-subtle">
            Your camera stays off until you enable it. When you request an
            expression check, five frames are sent to the server for analysis
            and aren’t saved. The result is an estimate, not a measure of how
            you feel.
          </p>
        </div>
      </div>
    </section>
  );
}

export default AboutSection;
