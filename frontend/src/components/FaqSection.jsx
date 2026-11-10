const questions = [
  {
    question: "What happens during an expression check?",
    answer:
      "After you enable the camera and choose Find my expression, MannKiDhun sends five frames to its server for analysis. The estimates are combined; if too few frames are usable or the results are inconsistent, you’ll be asked to try again. The result is not a reliable measure of how you feel.",
  },
  {
    question: "Is my camera footage stored?",
    answer:
      "Your camera is off until you enable it. The live preview stays in your browser. When you request an expression check, five frames are sent to the server for analysis and aren’t saved by the app.",
  },
  {
    question: "Can I use MannKiDhun without a camera?",
    answer:
      "Yes. Choose a vibe manually on the Discover page, or search for music with the Music Assistant. Camera access is optional.",
  },
  {
    question: "What if the check-in can’t detect a face?",
    answer:
      "You’ll see a message instead of an expression estimate. If you want to try again, move into good lighting, center your face, hold still, and retry.",
  },
  {
    question: "Why might a recommended video not play?",
    answer:
      "Some YouTube videos can’t be embedded or may be unavailable in your region. Use the link to open the video on YouTube, or search there for another track.",
  },
];

function FaqSection() {
  return (
    <section
      id="faq"
      className="faq-section grid grid-cols-[minmax(220px,0.75fr)_minmax(0,1.25fr)] items-start gap-[clamp(28px,7vw,88px)] mt-[62px] scroll-mt-6 px-1 pt-4 pb-[58px] max-[760px]:grid-cols-1 max-[760px]:gap-6 max-[760px]:mt-10 max-[760px]:pb-10"
      aria-labelledby="faq-title"
    >
      <div className="faq-heading">
        <p className="section-eyebrow">GOOD TO KNOW</p>
        <h2
          id="faq-title"
          className="mb-0 mt-3 max-w-[550px] font-display text-[clamp(22px,2.8vw,28px)] font-bold leading-[1.2] tracking-[-1.2px]"
        >
          A few things you might be wondering.
        </h2>
        <p className="mb-0 mt-3 text-[13px] leading-[1.7] text-subtle">
          Clear answers, so you can get back to the music.
        </p>
      </div>
      <div className="faq-list">
        {questions.map(({ question, answer }) => (
          <details className="faq-item" key={question}>
            <summary className="flex min-h-[62px] cursor-pointer list-none items-center justify-between gap-[18px] text-[13px] font-bold text-[#353147]">
              <span>{question}</span>
              <span
                className="faq-chevron grid h-[27px] w-[27px] shrink-0 place-items-center rounded-[9px] bg-[#f0ecff] text-[19px] font-medium text-[#7657e8] transition-transform duration-[160ms] ease-[ease]"
                aria-hidden="true"
              >
                +
              </span>
            </summary>
            <p className="mb-[19px] mr-[38px] mt-[-2px] max-w-[680px] text-xs leading-[1.8] text-subtle">
              {answer}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}

export default FaqSection;
