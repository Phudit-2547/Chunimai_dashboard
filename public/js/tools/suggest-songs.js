/**
 * Song suggestion tool for improving player rating.
 * Ported from ai_service/tools/suggest_songs.py
 */
import {
  RANK_FACTORS,
  getCoverUrl,
  getRankInfo,
  getNextRank,
  calculateSongRating,
  calcRating,
  buildConstantsMap,
  makeKey,
} from '../rating.js';

/**
 * Suggest songs to improve player rating.
 *
 * @param {object} playerData - Player data with profile, best, current, allRecords
 * @param {Array} allSongs - All songs from musicData
 * @param {object} options
 * @param {number} [options.targetRating] - Target rating to reach
 * @param {string} [options.mode="auto"] - "auto"|"target"|"best_effort"
 * @param {number} [options.maxSuggestions=5]
 * @param {string[]} [options.difficultyFilter]
 * @param {string} [options.version="CiRCLE"]
 * @param {string[]} [options.latestVersions=["CiRCLE","PRiSM+"]]
 * @returns {object} Suggestions with calculations
 */
export function suggestSongs(playerData, allSongs, options = {}) {
  const {
    targetRating = null,
    mode = 'auto',
    maxSuggestions = 5,
    difficultyFilter = null,
    version = 'CiRCLE',
    latestVersions = ['CiRCLE', 'PRiSM+'],
  } = options;

  // Build allRecords lookup for historical scores
  const allRecordsLookup = new Map();
  for (const record of playerData.allRecords || []) {
    const key = makeKey(record.title, record.chartType, record.difficulty);
    allRecordsLookup.set(key, record.score || 0);
  }

  // Build constants lookup
  const constants = buildConstantsMap(allSongs);

  // Get current rating (local calculation)
  const currentResult = calcRating(playerData, allSongs);
  const currentRating = currentResult.rating.total;

  // Calculate player's current constant range
  let maxPlayerConstant = 0;
  let minPlayerConstant = 999;
  for (const s of [...(playerData.best || []), ...(playerData.current || [])]) {
    const key = makeKey(s.title, s.chartType, s.difficulty);
    const c = constants.get(key) || 0;
    if (c > 0) {
      if (c > maxPlayerConstant) maxPlayerConstant = c;
      if (c < minPlayerConstant) minPlayerConstant = c;
    }
  }

  // Get existing songs
  const existing = new Set();
  for (const song of playerData.best || []) {
    existing.add(makeKey(song.title, song.chartType, song.difficulty));
  }
  for (const song of playerData.current || []) {
    existing.add(makeKey(song.title, song.chartType, song.difficulty));
  }

  // Get improvable songs (score < SSS+)
  const improvable = new Map();
  for (const song of [...(playerData.best || []), ...(playerData.current || [])]) {
    const key = makeKey(song.title, song.chartType, song.difficulty);
    if ((song.score || 0) < 1005000) {
      improvable.set(key, song.score || 0);
    }
  }

  const difficulties = difficultyFilter || ['master', 'expert', 'advanced'];

  // Get current section song ratings sorted (for new song replacement calc)
  const ratingSongs = [];
  for (const s of playerData.current || []) {
    const key = makeKey(s.title, s.chartType, s.difficulty);
    const c = constants.get(key) || 0;
    if (c > 0) {
      ratingSongs.push(calculateSongRating(c, s.score || 0));
    }
  }
  ratingSongs.sort((a, b) => a - b);

  // Find new song candidates
  const candidates = [];
  let newSongCount = 0;

  for (const song of allSongs) {
    const songVersion = song.releasedVersion || '';
    if (!latestVersions.includes(songVersion)) continue;

    for (const diff of difficulties) {
      if (!song[diff]) continue;

      const key = makeKey(song.title, song.chartType, diff);
      if (existing.has(key)) continue;

      const constant = song[diff].constant || 0;
      if (constant <= 0) continue;
      if (constant < minPlayerConstant) continue;

      const maxRating = calculateSongRating(constant, 1005000);

      const replaceIdx = newSongCount < ratingSongs.length ? newSongCount : ratingSongs.length - 1;
      const ratingReplaced = replaceIdx < ratingSongs.length ? ratingSongs[replaceIdx] : 0;
      const minRatingNeeded = ratingReplaced + 1;

      // Find minimum score/rank needed (iterate low to high)
      let minScoreNeeded = 0;
      let minRankNeeded = '';
      for (let i = RANK_FACTORS.length - 1; i >= 0; i--) {
        const [ms, factor, rankName] = RANK_FACTORS[i];
        const potential = Math.trunc(constant * (ms / 10000) * factor);
        if (potential >= minRatingNeeded) {
          minScoreNeeded = ms;
          minRankNeeded = rankName;
          break;
        }
      }
      if (minScoreNeeded === 0) {
        minScoreNeeded = 1005000;
        minRankNeeded = 'SSS+';
      }

      const targetRankRating = calculateSongRating(constant, minScoreNeeded);

      // Check allRecords for historical play
      const historyScore = allRecordsLookup.get(key) || 0;
      const historyRank = historyScore > 0 ? getRankInfo(historyScore) : null;
      const historyPctStr = historyScore > 0 ? `${(historyScore / 10000).toFixed(4)}%` : '';

      candidates.push({
        title: song.title,
        artist: song.artist || '',
        chartType: song.chartType,
        difficulty: diff,
        level: song[diff].level || '',
        constant,
        version: songVersion,
        image: song.image || '',
        cover_url: getCoverUrl(song.image || ''),
        max_rating: maxRating,
        min_rating_needed: minRatingNeeded,
        target_rank: minRankNeeded,
        target_score: minScoreNeeded,
        potential_rating: targetRankRating,
        rating_gain: targetRankRating - ratingReplaced,
        replaces: ratingReplaced,
        type: 'new',
        current_score: historyScore,
        current_rank: historyRank ? historyRank.rankName : '',
        current_pct_str: historyPctStr,
      });
      newSongCount++;
    }
  }

  // Find improvement candidates
  const improvements = [];
  for (const song of allSongs) {
    for (const diff of difficulties) {
      if (!song[diff]) continue;

      const key = makeKey(song.title, song.chartType, diff);
      if (!improvable.has(key)) continue;

      const constant = song[diff].constant || 0;
      if (constant <= 0) continue;

      const currentScore = improvable.get(key);
      const { rankName: currentRank, pct: currentPct } = getRankInfo(currentScore);
      const currentPctStr = `${currentPct.toFixed(4)}%`;
      const currentRatingSong = calculateSongRating(constant, currentScore);

      const { rankName: targetRank, minScore: targetScore } = getNextRank(currentScore);
      const potentialRating = calculateSongRating(constant, targetScore);
      const ratingGain = potentialRating - currentRatingSong;

      if (ratingGain > 0) {
        const maxRating = calculateSongRating(constant, 1005000);
        improvements.push({
          title: song.title,
          artist: song.artist || '',
          chartType: song.chartType,
          difficulty: diff,
          level: song[diff].level || '',
          constant,
          image: song.image || '',
          cover_url: getCoverUrl(song.image || ''),
          current_score: currentScore,
          current_rank: currentRank,
          current_pct: currentPct,
          current_pct_str: currentPctStr,
          target_rank: targetRank,
          target_score: targetScore,
          potential_rating: potentialRating,
          max_rating: maxRating,
          rating_gain: ratingGain,
          type: 'improve',
        });
      }
    }
  }

  candidates.sort((a, b) => b.potential_rating - a.potential_rating);
  improvements.sort((a, b) => b.rating_gain - a.rating_gain);

  const isTargetMode = mode === 'target' || (mode === 'auto' && targetRating !== null);

  const suggestions = {
    mode: isTargetMode ? 'target' : 'best_effort',
    current_rating: currentRating,
    target_rating: targetRating,
  };

  if (isTargetMode) {
    return _buildTargetMode(suggestions, playerData, constants, improvements, candidates, targetRating, currentRating);
  }

  // Best-effort mode
  const improvementsSorted = [...improvements].sort((a, b) => a.rating_gain - b.rating_gain);
  suggestions.improvements = improvementsSorted.slice(0, maxSuggestions);
  suggestions.new_songs = candidates.slice(0, maxSuggestions);
  suggestions.message = `Found ${candidates.length} new songs and ${improvements.length} improvements`;
  return suggestions;
}

/**
 * Build target mode response — find the easiest path to reach target rating.
 */
function _buildTargetMode(suggestions, playerData, constants, improvements, candidates, targetRating, currentRating) {
  const ratingNeeded = targetRating - currentRating;

  // Get current top 50 ratings
  const top50Ratings = [];
  for (const s of [...(playerData.best || []), ...(playerData.current || [])]) {
    const key = makeKey(s.title, s.chartType, s.difficulty);
    const c = constants.get(key) || 0;
    if (c > 0) {
      top50Ratings.push(calculateSongRating(c, s.score || 0));
    }
  }
  top50Ratings.sort((a, b) => a - b);

  // Build all song options
  const allSongOptions = [];

  for (const s of improvements) {
    const constant = s.constant || 0;
    if (constant <= 0) continue;
    const maxRating = calculateSongRating(constant, 1005000);
    const currentRatingSong = s.potential_rating - s.rating_gain;
    const potentialGain = maxRating - currentRatingSong;

    allSongOptions.push({
      title: s.title,
      artist: s.artist || '',
      level: s.level || '',
      image: s.image || '',
      constant,
      difficulty: s.difficulty || '',
      chartType: s.chartType || '',
      current_rating: currentRatingSong,
      current_score: s.current_score || 0,
      current_rank: s.current_rank || '',
      current_pct: s.current_pct || 0,
      current_pct_str: s.current_pct_str || '0.0000%',
      max_rating: maxRating,
      potential_gain: potentialGain,
      type: 'improve',
    });
  }

  for (const s of candidates) {
    const constant = s.constant || 0;
    if (constant <= 0) continue;
    const maxRating = calculateSongRating(constant, 1005000);
    const potentialGain = top50Ratings.length > 0 ? maxRating - top50Ratings[0] : maxRating;

    allSongOptions.push({
      title: s.title || '',
      artist: s.artist || '',
      level: s.level || '',
      image: s.image || '',
      version: s.version || '',
      constant,
      difficulty: s.difficulty || '',
      chartType: s.chartType || '',
      current_rating: 0,
      current_score: s.current_score || 0,
      current_rank: s.current_rank || '',
      current_pct_str: s.current_pct_str || '',
      max_rating: maxRating,
      potential_gain: potentialGain,
      type: 'new',
    });
  }

  // Sort by potential gain descending
  allSongOptions.sort((a, b) => b.potential_gain - a.potential_gain);

  const selected = [];
  let remaining = ratingNeeded;
  let newSongsAdded = 0;

  for (const songOpt of allSongOptions) {
    if (remaining <= 0) break;

    const maxR = songOpt.max_rating;

    if (songOpt.type === 'improve') {
      const currentR = songOpt.current_rating;
      const potentialGain = maxR - currentR;
      if (potentialGain < 10) continue;

      const actualGain = Math.min(potentialGain, remaining);
      const targetR = currentR + actualGain;

      // Update top50: replace old rating with new
      for (let i = 0; i < top50Ratings.length; i++) {
        if (Math.abs(top50Ratings[i] - currentR) < 1) {
          top50Ratings[i] = targetR;
          break;
        }
      }
      top50Ratings.sort((a, b) => a - b);

      // Find minimum score/rank needed
      let minScore = 0;
      let minRank = '';
      for (const [ms, factor, rankName] of RANK_FACTORS) {
        const potential = Math.trunc(songOpt.constant * (ms / 10000) * factor);
        if (potential >= targetR) {
          minScore = ms;
          minRank = rankName;
          break;
        }
      }
      if (minScore === 0) { minScore = 1005000; minRank = 'SSS+'; }

      selected.push({
        song: {
          title: songOpt.title,
          artist: songOpt.artist,
          level: songOpt.level,
          image: songOpt.image,
          cover_url: getCoverUrl(songOpt.image || ''),
          version: songOpt.version || '',
          difficulty: songOpt.difficulty,
          chartType: songOpt.chartType,
          constant: songOpt.constant,
          target_rank: minRank,
          target_score: minScore,
          achievement: Math.round(minScore / 100) / 100,
          potential_rating: targetR,
        },
        gain_needed: actualGain,
        max_gain: potentialGain,
        type: songOpt.type,
        current_score: songOpt.current_score,
        current_rank: songOpt.current_rank,
        current_pct_str: songOpt.current_pct_str || '',
      });
      remaining -= actualGain;

    } else {
      // New song: enters top 50, pushes out lowest
      if (maxR <= top50Ratings[0]) continue;

      const lowestPushed = top50Ratings[0];
      const potentialGain = maxR - lowestPushed;
      if (potentialGain < 10) continue;

      const actualGain = Math.min(potentialGain, remaining);
      const targetR = lowestPushed + actualGain;

      let minScore = 0;
      let minRank = '';
      for (const [ms, factor, rankName] of RANK_FACTORS) {
        const potential = Math.trunc(songOpt.constant * (ms / 10000) * factor);
        if (potential >= targetR) {
          minScore = ms;
          minRank = rankName;
          break;
        }
      }
      if (minScore === 0) { minScore = 1005000; minRank = 'SSS+'; }

      // Update top50: remove lowest, add new
      top50Ratings.shift();
      top50Ratings.push(targetR);
      top50Ratings.sort((a, b) => a - b);
      newSongsAdded++;

      selected.push({
        song: {
          title: songOpt.title,
          artist: songOpt.artist,
          level: songOpt.level,
          image: songOpt.image,
          cover_url: getCoverUrl(songOpt.image || ''),
          version: songOpt.version || '',
          difficulty: songOpt.difficulty,
          chartType: songOpt.chartType,
          constant: songOpt.constant,
          target_rank: minRank,
          target_score: minScore,
          achievement: Math.round(minScore / 100) / 100,
          potential_rating: targetR,
        },
        gain_needed: actualGain,
        max_gain: potentialGain,
        type: songOpt.type,
        current_score: songOpt.current_score,
        current_rank: songOpt.current_rank,
        current_pct_str: songOpt.current_pct_str || '',
      });
      remaining -= actualGain;
    }
  }

  const gainAchieved = selected.reduce((sum, s) => sum + s.gain_needed, 0);
  const projected = currentRating + gainAchieved;

  suggestions.rating_needed = ratingNeeded;
  suggestions.songs = selected;
  suggestions.projected_rating = projected;

  if (projected >= targetRating) {
    suggestions.message = `Here's the easiest path to reach ${targetRating}! (+${gainAchieved} rating from ${selected.length} songs)`;
  } else {
    suggestions.message = `Best path found: projected ${projected} (+${gainAchieved} from ${selected.length} songs). Need ${targetRating - projected} more for ${targetRating}.`;
  }

  return suggestions;
}
