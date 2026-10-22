import React from 'react';

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
}) {
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
              {bowlingSquad.map((p) => (
                <option key={p.player_id} value={p.player_id}>
                  {p.player?.name}
                </option>
              ))}
            </select>
          </div>
          <div className="player-stats">
            <span className="runs-balls">
              {bowlerStat.overs}-{bowlerStat.maidens}-{bowlerStat.runs_conceded}-<strong>{bowlerStat.wickets}</strong>
            </span>
            <span className="sub-stat">Econ: {bowlerStat.economy_rate}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
