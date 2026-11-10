import { useEffect, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";
import AboutSection from "./AboutSection.jsx";
import FaqSection from "./FaqSection.jsx";

function HomePage({ theme, onToggleTheme }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/session")
      .then((response) => {
        if (!response.ok) throw new Error("Could not verify your session.");
        return response.json();
      })
      .then(({ user: currentUser }) => {
        if (active) setUser(currentUser || null);
      })
      .catch((error) => {
        if (active) console.error("Could not verify the MannKiDhun session:", error);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell home-shell">
      <div className="page-shell mx-auto min-h-screen w-[min(1120px,calc(100%-40px))]">
        <Header theme={theme} onToggleTheme={onToggleTheme} user={user} />
        <main>
          <section
            className="home-hero grid min-h-[490px] grid-cols-[minmax(0,1fr)_minmax(300px,0.88fr)] items-center gap-[clamp(32px,7vw,88px)] pt-[46px] pb-[52px] max-[760px]:min-h-0 max-[760px]:grid-cols-1 max-[760px]:gap-9 max-[760px]:pt-14 max-[760px]:pb-[35px]"
            aria-labelledby="home-title"
          >
            <div className="home-hero-copy">
              <p className="eyebrow">
                <span className="eyebrow-dot" />
                EVERY FEELING HAS A TUNE
              </p>
              <h1
                id="home-title"
                className="mt-5 max-w-[590px] font-display text-[clamp(40px,6vw,65px)] font-extrabold leading-[1.05] tracking-[-0.065em] max-[760px]:max-w-[560px] max-[760px]:text-[clamp(40px,10vw,58px)]"
              >
                Your Music. <span>Your Vibe.</span> Your World.
              </h1>
              <p className="home-hero-description mt-[22px] max-w-[465px] text-[15px] leading-[1.8] text-subtle">
                Explore music for the moment you’re in. Choose a vibe yourself,
                or opt into a brief expression estimate for a starting suggestion.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-x-[21px] gap-y-4 max-[480px]:items-start max-[480px]:flex-col">
                <a className="nav-cta home-primary-cta" href="/signup">
                  Discover Your Vibe <span aria-hidden="true">→</span>
                </a>
                <a
                  className="home-secondary-cta text-xs font-bold text-[#625e73] no-underline hover:text-accent hover:underline hover:underline-offset-4"
                  href="#features"
                >
                  Explore Music
                </a>
              </div>
              <div className="mt-7 flex items-center gap-2 text-[11px] text-[#898696]">
                <span className="text-[15px] text-[#8d71ed]" aria-hidden="true">✦</span>
                A small moment of self-discovery, whenever you need it.
              </div>
            </div>
            <div className="home-art" aria-label="A music-inspired mood visual">
              <div className="home-art-glow" />
              <div className="home-art-orbit home-art-orbit-one" />
              <div className="home-art-orbit home-art-orbit-two" />
              <div className="home-art-note" aria-hidden="true">♫</div>
              <span className="home-art-chip home-chip-top">follow your feeling</span>
              <span className="home-art-chip home-chip-bottom">made for this moment</span>
              <div className="home-waveform" aria-hidden="true">
                {[24, 42, 30, 55, 75, 43, 62, 88, 48, 69, 37, 57, 28, 46, 22].map(
                  (height, index) => (
                    <span key={index} style={{ height: `${height}%` }} />
                  ),
                )}
              </div>
            </div>
          </section>

          <section
            id="features"
            className="home-benefits grid grid-cols-3 gap-4 p-6 max-[760px]:grid-cols-1 max-[760px]:gap-3 max-[760px]:p-[18px]"
            aria-label="Why MannKiDhun"
          >
            <article className="home-benefit flex items-start gap-3 p-1.5">
              <span className="home-benefit-icon" aria-hidden="true">◉</span>
              <div>
                <h2 className="mb-0 mt-px font-display text-[13px] font-extrabold">
                  Music that meets your mood
                </h2>
                <p className="mb-0 mt-1.5 text-[11px] leading-[1.65] text-subtle">
                  Get a music suggestion from your chosen vibe or an optional expression check-in.
                </p>
              </div>
            </article>
            <article className="home-benefit flex items-start gap-3 p-1.5">
              <span className="home-benefit-icon home-benefit-lilac" aria-hidden="true">♫</span>
              <div>
                <h2 className="mb-0 mt-px font-display text-[13px] font-extrabold">
                  Your vibe, your choice
                </h2>
                <p className="mb-0 mt-1.5 text-[11px] leading-[1.65] text-subtle">
                  Choose a vibe yourself whenever you prefer not to use the camera.
                </p>
              </div>
            </article>
            <article className="home-benefit flex items-start gap-3 p-1.5" id="home-privacy">
              <span className="home-benefit-icon home-benefit-peach" aria-hidden="true">♡</span>
              <div>
                <h2 className="mb-0 mt-px font-display text-[13px] font-extrabold">
                  Privacy comes first
                </h2>
                <p className="mb-0 mt-1.5 text-[11px] leading-[1.65] text-subtle">
                  Five frames are sent for analysis only when you request an expression check. They aren’t saved.
                </p>
              </div>
            </article>
          </section>

          <section
            className="home-how-section grid grid-cols-[minmax(210px,0.8fr)_minmax(0,1.5fr)] items-center gap-[34px] mt-[58px] p-[clamp(24px,5vw,46px)] max-[760px]:grid-cols-1 max-[760px]:gap-[23px] max-[760px]:mt-9"
            aria-labelledby="home-how-title"
          >
            <div className="home-how-heading">
              <p className="section-eyebrow">A BETTER WAY TO PRESS PLAY</p>
              <h2
                id="home-how-title"
                className="mb-0 mt-[11px] font-display text-[clamp(22px,3vw,31px)] font-extrabold leading-[1.2] tracking-[-1px]"
              >
                A soundtrack that starts with you.
              </h2>
              <p className="mb-0 mt-[11px] text-xs leading-[1.7] text-[#b6b1c2]">
                Start with your own choice, or use an expression check-in if you want to.
              </p>
            </div>
            <div className="home-how-steps grid grid-cols-3 gap-3 max-[520px]:grid-cols-1">
              <article className="min-h-[143px] rounded-[15px] border border-white/[8%] bg-white/[4%] px-[15px] py-[18px] max-[520px]:min-h-0">
                <span className="text-[11px] font-extrabold tracking-[1px] text-[#c3aeff]">01</span>
                <h3 className="mb-0 mt-[18px] text-[13px] font-bold">Choose how to check in</h3>
                <p className="mb-0 mt-[7px] text-[10px] leading-[1.6] text-[#b6b1c2]">
                  Pick a vibe yourself or opt into a brief expression estimate.
                </p>
              </article>
              <article className="min-h-[143px] rounded-[15px] border border-white/[8%] bg-white/[4%] px-[15px] py-[18px] max-[520px]:min-h-0">
                <span className="text-[11px] font-extrabold tracking-[1px] text-[#c3aeff]">02</span>
                <h3 className="mb-0 mt-[18px] text-[13px] font-bold">Find a starting point</h3>
                <p className="mb-0 mt-[7px] text-[10px] leading-[1.6] text-[#b6b1c2]">
                  Explore a music suggestion based on the vibe you chose.
                </p>
              </article>
              <article className="min-h-[143px] rounded-[15px] border border-white/[8%] bg-white/[4%] px-[15px] py-[18px] max-[520px]:min-h-0">
                <span className="text-[11px] font-extrabold tracking-[1px] text-[#c3aeff]">03</span>
                <h3 className="mb-0 mt-[18px] text-[13px] font-bold">Take it from there</h3>
                <p className="mb-0 mt-[7px] text-[10px] leading-[1.6] text-[#b6b1c2]">
                  Preview the suggestion or continue exploring on YouTube.
                </p>
              </article>
            </div>
          </section>

          <AboutSection checkInHref="/signup" />
          <FaqSection />

          <section className="home-bottom-cta flex min-h-[158px] items-center justify-between gap-5 mt-7 px-[34px] py-7 max-[760px]:min-h-[140px] max-[760px]:p-[23px] max-[480px]:items-start max-[480px]:flex-col max-[480px]:justify-center">
            <div>
              <p className="section-eyebrow">MANNKIDHUN · EVERY FEELING HAS A TUNE</p>
              <h2 className="mt-[9px] font-display text-[clamp(18px,3vw,25px)] font-extrabold tracking-[-0.8px]">
                Find the sound that feels like yours.
              </h2>
            </div>
            <a className="nav-cta" href="/signup">
              Discover Your Vibe <span aria-hidden="true">→</span>
            </a>
          </section>
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

export default HomePage;
