import React from 'react';

export default function ScoreBanner({ match, innings, scorecard, matchSummary }) {
  if (!match || !innings) return null;

  const battingTeam = innings.batting_team?.name || 'Batting Team';
  const score = scorecard?.total_runs ?? 0;
  const wickets = scorecard?.wickets_lost ?? 0;
  const overs = scorecard?.overs ?? '0.0';
  const runRate = scorecard?.run_rate ?? '0.0';

  // Calculate RRR for 2nd innings
  let rrr = null;
  let runsNeeded = null;
  let ballsLeft = null;

  if (innings.innings_number === 2 && innings.target_runs && innings.max_overs) {
    const [ovs, b] = (scorecard?.overs || '0.0').split('.').map(Number);
    const legalBallsBowled = ovs * 6 + b;
    const totalBalls = innings.max_overs * 6;
    ballsLeft = Math.max(0, totalBalls - legalBallsBowled);
    runsNeeded = Math.max(0, innings.target_runs - score);
    if (ballsLeft > 0) {
      rrr = ((runsNeeded / ballsLeft) * 6).toFixed(2);
    }
  }

  const isCompleted = match.status === 'COMPLETED' || innings.status === 'COMPLETED';

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
        <span className="badge innings-badge">Innings {innings.innings_number}</span>
      </div>

      {/* Match Result Banner */}
      {match.status === 'COMPLETED' && matchSummary && (
        <div className="match-result-banner">
          🏆 <strong>{matchSummary}</strong>
        </div>
      )}

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
            <>
              <div className="stat-pill">
                <span className="stat-label">Target</span>
                <span className="stat-value">{innings.target_runs}</span>
              </div>
              {rrr !== null && !isCompleted && (
                <div className="stat-pill highlight-pill">
                  <span className="stat-label">RRR</span>
                  <span className="stat-value">{rrr}</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Chasing equation bar */}
      {innings.innings_number === 2 && innings.target_runs && !isCompleted && runsNeeded !== null && (
        <div className="chase-equation">
          <span>
            Need <strong>{runsNeeded}</strong> runs in <strong>{ballsLeft}</strong> balls to win
          </span>
        </div>
      )}

      {match.venue && <div className="banner-venue">📍 {match.venue}</div>}
    </div>
  );
}
