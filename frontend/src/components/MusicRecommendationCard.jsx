function MusicRecommendationCard({ mood, songId }) {
  const songUrl = songId
    ? `https://www.youtube.com/watch?v=${songId}`
    : "";
  const embedUrl = songId
    ? `https://www.youtube-nocookie.com/embed/${songId}?autoplay=1&playsinline=1`
    : "";
  const searchUrl = mood
    ? `https://www.youtube.com/results?search_query=${encodeURIComponent(`${mood} mood music`)}`
    : "";

  return (
    <article className="music-card" id="faq-video">
      <div className="card-heading relative z-10">
        <span className="step-number step-number-dark">02</span>
        <div>
          <p className="card-kicker text-[#b6afc9]">THEN, THE SOUND</p>
          <h2 className="mt-1 font-display text-[17px] font-bold tracking-tight text-white">
            Make it a moment
          </h2>
        </div>
        <span className="ml-auto text-2xl text-[#c3aeff]" aria-hidden="true">
          ✳
        </span>
      </div>

      {!songId ? (
        <div className="music-visual" aria-hidden="true">
          <div className="music-orbit orbit-one" />
          <div className="music-orbit orbit-two" />
          <div className="music-orbit orbit-three" />
          <div className="music-note">♫</div>
          <span className="floating-note note-left">♪</span>
          <span className="floating-note note-right">♪</span>
        </div>
      ) : (
        <div className="music-player">
          <iframe
            key={songId}
            src={embedUrl}
            title={`Music recommendation for ${mood}`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
          />
        </div>
      )}

      <div className="py-4">
        <p className="card-kicker text-[#b9acd9]">YOUR NEXT LISTEN</p>
        <h3 className="mt-1 font-display text-[17px] font-bold text-white">
          {mood ? `A little ${mood} in the mix.` : "A song that feels like you."}
        </h3>
        <p className="mt-1 text-sm text-[#b7b2c5]">
          {mood
            ? "A fresh pick, just for this moment."
            : "Let the music meet you where you are."}
        </p>
      </div>

      {songUrl && (
        <div className="music-links mb-2">
          <a href={songUrl} target="_blank" rel="noopener noreferrer">
            Open this recommendation on YouTube{" "}
            <span aria-hidden="true">↗</span>
          </a>
          <a href={searchUrl} target="_blank" rel="noopener noreferrer">
            Find another {mood} song <span aria-hidden="true">↗</span>
          </a>
        </div>
      )}
      <p className="mt-auto border-t border-white/10 pt-3 text-[11px] text-[#aaa4bb]">
        This suggestion is based on an expression estimate, not a measure of how you feel.
      </p>
    </article>
  );
}

export default MusicRecommendationCard;
