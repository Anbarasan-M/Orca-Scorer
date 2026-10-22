import React from 'react';

export default function ScoreBanner({ match, innings, scorecard }) {
  if (!match || !innings) return null;

  const battingTeam = innings.batting_team?.name || 'Batting Team';
  const bowlingTeam = innings.bowling_team?.name || 'Bowling Team';
  const score = scorecard?.total_runs ?? 0;
  const wickets = scorecard?.wickets_lost ?? 0;
  const overs = scorecard?.overs ?? '0.0';
  const runRate = scorecard?.run_rate ?? '0.0';

  return (
    <div className="score-banner">
      <div className="banner-top">
        <span className="badge format-badge">{match.format}</span>
        <span className="match-title">
          {match.team1?.name} vs {match.team2?.name}
        </span>
        <span className={`badge status-badge ${innings.status.toLowerCase()}`}>
          {innings.status}
        </span>
      </div>

      <div className="banner-main">
        <div className="main-team">
          <span className="batting-label">{battingTeam}</span>
          <div className="score-display">
            <span className="runs-wkts">
              {score}/{wickets}
            </span>
            <span className="overs-display">({overs} ov)</span>
          </div>
        </div>

        <div className="banner-stats">
          <div className="stat-pill">
            <span className="stat-label">CRR</span>
            <span className="stat-value">{runRate}</span>
          </div>
          {innings.target_runs && (
            <div className="stat-pill">
              <span className="stat-label">Target</span>
              <span className="stat-value">{innings.target_runs}</span>
            </div>
          )}
        </div>
      </div>

      {match.venue && <div className="banner-venue">📍 {match.venue}</div>}
    </div>
  );
}
