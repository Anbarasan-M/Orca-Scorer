import React, { useState } from 'react';
import PlayerStatsModal from './PlayerStatsModal';

export default function BattersBowlerHUD({
  strikerId,
  nonStrikerId,
  bowlerId,
  onStrikerChange,
  onNonStrikerChange,
  onBowlerChange,
  battingSquad,
  bowlingSquad,
  scorecard,
  deliveries = [],
  maxOvers = null,
}) {
  const [inspectingPlayerId, setInspectingPlayerId] = useState(null);

  // Determine previous over's bowler (cannot bowl consecutive overs)
  let lastOverBowlerId = null;
  if (deliveries && deliveries.length > 0) {
    const latestDelivery = deliveries[deliveries.length - 1];
    const currentOverNum = latestDelivery.over_number;
    const legalBallsInCurrentOver = deliveries.filter(
      (d) => d.over_number === currentOverNum && d.is_legal
    ).length;

    if (legalBallsInCurrentOver === 6) {
      // Over just finished: this latest bowler cannot bowl the NEXT over
      lastOverBowlerId = latestDelivery.bowler_id;
    } else if (currentOverNum > 1 && legalBallsInCurrentOver === 0) {
      // At the start of a new over: find bowler of previous over
      const prevDelivery = deliveries.find((d) => d.over_number === currentOverNum - 1);
      if (prevDelivery) lastOverBowlerId = prevDelivery.bowler_id;
    }
  }

  // Quota calculation (max 20% of innings total overs in limited overs)
  const maxQuota = maxOvers ? Math.max(1, Math.ceil(maxOvers / 5)) : null;

  const battingStats = scorecard?.batting || [];
  const bowlingStats = scorecard?.bowling || [];

  const getBatterStat = (playerId) => {
    return battingStats.find((b) => b.player_id === playerId) || {
      runs: 0,
      balls_faced: 0,
      fours: 0,
      sixes: 0,
      strike_rate: 0,
    };
  };

  const getBowlerStat = (playerId) => {
    return bowlingStats.find((b) => b.player_id === playerId) || {
      overs: '0.0',
      maidens: 0,
      runs_conceded: 0,
      wickets: 0,
      economy_rate: 0,
    };
  };

  const strikerStat = getBatterStat(strikerId);
  const nonStrikerStat = getBatterStat(nonStrikerId);
  const bowlerStat = getBowlerStat(bowlerId);

  return (
    <div className="hud-container">
      {/* Batters Box */}
      <div className="hud-card batters-card">
        <div className="hud-header">
          <span>🏏 Batters</span>
        </div>

        {/* Striker */}
        <div className="player-row active-striker">
          <div className="player-info">
            <span className="striker-dot">*</span>
            <select
              value={strikerId || ''}
              onChange={(e) => onStrikerChange(Number(e.target.value))}
              className="player-select"
            >
              <option value="" disabled>Select Striker</option>
              {battingSquad.map((p) => (
                <option key={p.player_id} value={p.player_id} disabled={p.player_id === nonStrikerId}>
                  {p.player?.name}
                </option>
              ))}
            </select>
            {strikerId && (
              <button
                type="button"
                className="btn-stat-icon"
                title="View Career Stats"
                onClick={() => setInspectingPlayerId(strikerId)}
              >
                📊
              </button>
            )}
          </div>
          <div className="player-stats">
            <span className="runs-balls">
              <strong>{strikerStat.runs}</strong> ({strikerStat.balls_faced})
            </span>
            <span className="sub-stat">
              4s: {strikerStat.fours} | 6s: {strikerStat.sixes} | SR: {strikerStat.strike_rate}
            </span>
          </div>
        </div>

        {/* Non-Striker */}
        <div className="player-row">
          <div className="player-info">
            <span className="non-striker-dot"> </span>
            <select
              value={nonStrikerId || ''}
              onChange={(e) => onNonStrikerChange(Number(e.target.value))}
              className="player-select"
            >
              <option value="" disabled>Select Non-Striker</option>
              {battingSquad.map((p) => (
                <option key={p.player_id} value={p.player_id} disabled={p.player_id === strikerId}>
                  {p.player?.name}
                </option>
              ))}
            </select>
            {nonStrikerId && (
              <button
                type="button"
                className="btn-stat-icon"
                title="View Career Stats"
                onClick={() => setInspectingPlayerId(nonStrikerId)}
              >
                📊
              </button>
            )}
          </div>
          <div className="player-stats">
            <span className="runs-balls">
              <strong>{nonStrikerStat.runs}</strong> ({nonStrikerStat.balls_faced})
            </span>
            <span className="sub-stat">
              4s: {nonStrikerStat.fours} | 6s: {nonStrikerStat.sixes} | SR: {nonStrikerStat.strike_rate}
            </span>
          </div>
        </div>

        {/* Active Partnership Badge */}
        {scorecard?.current_partnership && (
          <div className="partnership-badge">
            <span className="partnership-label">🤝 Partnership:</span>
            <span className="partnership-highlight">
              <strong>{scorecard.current_partnership.runs}</strong> runs ({scorecard.current_partnership.balls}b)
            </span>
            {scorecard.current_partnership.batter1 && scorecard.current_partnership.batter2 && (
              <span className="partnership-breakdown">
                ({scorecard.current_partnership.batter1.player_name?.split(' ')[0]}: {scorecard.current_partnership.batter1.runs}, {scorecard.current_partnership.batter2.player_name?.split(' ')[0]}: {scorecard.current_partnership.batter2.runs})
              </span>
            )}
          </div>
        )}
      </div>

      {/* Bowler Box */}
      <div className="hud-card bowler-card">
        <div className="hud-header">
          <span>🎯 Bowler</span>
        </div>
        <div className="player-row">
          <div className="player-info">
            <select
              value={bowlerId || ''}
              onChange={(e) => onBowlerChange(Number(e.target.value))}
              className="player-select"
            >
              <option value="" disabled>Select Bowler</option>
              {bowlingSquad.map((p) => {
                const bStat = getBowlerStat(p.player_id);
                const [ovsStr] = (bStat.overs || '0.0').split('.');
                const fullOversBowled = parseInt(ovsStr, 10) || 0;
                const isConsecutiveRestricted = lastOverBowlerId === p.player_id;
                const isQuotaReached = maxQuota !== null && fullOversBowled >= maxQuota && bowlerId !== p.player_id;

                let disabledReason = '';
                if (isConsecutiveRestricted) disabledReason = ' (Bowled last over)';
                else if (isQuotaReached) disabledReason = ` (Max ${maxQuota} ov bowled)`;

                return (
                  <option
                    key={p.player_id}
                    value={p.player_id}
                    disabled={isConsecutiveRestricted || isQuotaReached}
                  >
                    {p.player?.name} ({bStat.overs} ov){disabledReason}
                  </option>
                );
              })}
            </select>
            {bowlerId && (
              <button
                type="button"
                className="btn-stat-icon"
                title="View Career Stats"
                onClick={() => setInspectingPlayerId(bowlerId)}
              >
                📊
              </button>
            )}
          </div>
          <div className="player-stats">
            <span className="runs-balls">
              {bowlerStat.overs}-{bowlerStat.maidens}-{bowlerStat.runs_conceded}-<strong>{bowlerStat.wickets}</strong>
            </span>
            <span className="sub-stat">Econ: {bowlerStat.economy_rate}</span>
          </div>
        </div>
      </div>

      {/* Player Career Stats Modal */}
      <PlayerStatsModal
        playerId={inspectingPlayerId}
        onClose={() => setInspectingPlayerId(null)}
      />
    </div>
  );
}
