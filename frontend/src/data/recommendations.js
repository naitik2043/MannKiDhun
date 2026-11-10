export const recommendations = {
  happy: ["ZbZSe6N_BXs", "y6Sxv-sUYtM"],
  sad: ["RB-RcX5DS5A", "RgKAFK5djSk"],
  angry: ["tAGnKpE4NCI", "hTWKbfoikeg"],
  neutral: ["fLexgOxsZu0", "kXYiU_JCYtU"],
  surprise: ["ScNNfyq3d_w", "pRpeEdMmmQ0"],
  rock: ["hTWKbfoikeg", "tAGnKpE4NCI"],
};

export function chooseSong(mood) {
  const songs = recommendations[mood];
  if (!songs) {
    throw new Error(`No music recommendations are configured for "${mood}".`);
  }
  return songs[Math.floor(Math.random() * songs.length)];
}
