/**
 * Maimai rating calculation module.
 * Ported from ai_service/rating.py
 */

export const COVER_BASE_URL = 'https://maimai.wonderhoy.me/api/imageProxy?img=';

// Rank factor table: [minScore, factor, name] (ordered high to low)
export const RANK_FACTORS = [
  [1005000, 0.224, 'SSS+'],
  [1000000, 0.216, 'SSS'],
  [995000, 0.211, 'SS+'],
  [990000, 0.208, 'SS'],
  [980000, 0.203, 'S+'],
  [970000, 0.200, 'S'],
  [940000, 0.168, 'AAA'],
  [900000, 0.152, 'AA'],
  [800000, 0.136, 'A'],
];

export function getCoverUrl(imageFilename) {
  if (!imageFilename) return '';
  return `${COVER_BASE_URL}${imageFilename}`;
}

/**
 * Get rank name and percentage from score.
 * @returns {{ rankName: string, pct: number }}
 */
export function getRankInfo(score) {
  let rankName = 'Below A';
  const pct = score / 10000;
  for (const [minScore, , name] of RANK_FACTORS) {
    if (score >= minScore) {
      rankName = name;
      break;
    }
  }
  return { rankName, pct };
}

/**
 * Get rank factor based on score.
 */
export function getRankFactor(score) {
  for (const [minScore, factor] of RANK_FACTORS) {
    if (score >= minScore) return factor;
  }
  return 0.0;
}

/**
 * Get the next rank up from current score.
 * @returns {{ rankName: string, minScore: number }}
 */
export function getNextRank(score) {
  let currentIdx = -1;
  for (let i = 0; i < RANK_FACTORS.length; i++) {
    if (score >= RANK_FACTORS[i][0]) {
      currentIdx = i;
      break;
    }
  }
  if (currentIdx > 0) {
    const [nextMinScore, , nextName] = RANK_FACTORS[currentIdx - 1];
    return { rankName: nextName, minScore: nextMinScore };
  }
  return { rankName: 'SSS+', minScore: 1005000 };
}

/**
 * Calculate rating for a single song.
 * rating = int(constant * achievement * factor)
 * Achievement capped at 100.5% for SSS+.
 * Uses Math.trunc (truncation, not rounding) to match the game.
 */
export function calculateSongRating(constant, score) {
  let achievement, factor;
  if (score >= 1005000) {
    achievement = 100.5;
    factor = 0.224;
  } else {
    achievement = score / 10000;
    factor = getRankFactor(score);
  }
  return Math.trunc(constant * achievement * factor);
}

/**
 * Build a constants lookup Map from allSongs (musicData).
 * Key: "title|chartType|difficulty" → constant value
 */
export function buildConstantsMap(allSongs) {
  const constants = new Map();
  const diffs = ['basic', 'advanced', 'expert', 'master', 'remaster'];
  for (const song of allSongs) {
    for (const diff of diffs) {
      if (song[diff]) {
        const key = `${song.title}|${song.chartType}|${diff}`;
        constants.set(key, song[diff].constant || 0);
      }
    }
  }
  return constants;
}

/**
 * Make a constants key from song fields.
 */
export function makeKey(title, chartType, difficulty) {
  return `${title}|${chartType}|${difficulty}`;
}

/**
 * Calculate total rating from a list of songs.
 */
export function calculateTotalRating(songs, constants) {
  let total = 0;
  for (const song of songs) {
    const key = makeKey(song.title, song.chartType, song.difficulty);
    const constant = constants.get(key) || 0;
    if (constant > 0) {
      total += calculateSongRating(constant, song.score || 0);
    }
  }
  return total;
}

/**
 * Calculate full rating breakdown locally.
 * Replaces the external API call to maimai.wonderhoy.me/api/calcRating.
 *
 * @param {object} playerData - { best: [...], current: [...], ... }
 * @param {Array} allSongs - musicData array
 * @returns {{ rating: { total, bestSum, currentSum }, best: [...], current: [...] }}
 */
export function calcRating(playerData, allSongs) {
  const constants = buildConstantsMap(allSongs);

  const best = (playerData.best || []).map(song => {
    const key = makeKey(song.title, song.chartType, song.difficulty);
    const constant = constants.get(key) || 0;
    const rating = constant > 0 ? calculateSongRating(constant, song.score || 0) : 0;
    return { ...song, rating };
  });

  const current = (playerData.current || []).map(song => {
    const key = makeKey(song.title, song.chartType, song.difficulty);
    const constant = constants.get(key) || 0;
    const rating = constant > 0 ? calculateSongRating(constant, song.score || 0) : 0;
    return { ...song, rating };
  });

  const bestSum = best.reduce((sum, s) => sum + s.rating, 0);
  const currentSum = current.reduce((sum, s) => sum + s.rating, 0);

  return {
    rating: { total: bestSum + currentSum, bestSum, currentSum },
    best,
    current,
  };
}
