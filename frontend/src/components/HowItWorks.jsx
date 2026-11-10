const steps = [
  ["01", "Choose your path.", "Pick a vibe yourself or enable an optional camera check-in."],
  ["02", "Find a starting point.", "Explore a music suggestion based on the vibe you chose."],
  ["03", "Keep exploring.", "Preview the suggestion or open it on YouTube."],
];

function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="how-it-works mt-7"
      aria-labelledby="how-title"
    >
      <div>
        <p className="card-kicker">A SIMPLE WAY TO DISCOVER</p>
        <h2
          id="how-title"
          className="mt-1 font-display text-base font-bold tracking-tight"
        >
          A moment for yourself.
        </h2>
      </div>
      {steps.map(([number, title, copy]) => (
        <div className="how-step" key={number}>
          <span className="how-icon">{number}</span>
          <p>
            <strong>{title}</strong>
            {copy}
          </p>
        </div>
      ))}
    </section>
  );
}

export default HowItWorks;
