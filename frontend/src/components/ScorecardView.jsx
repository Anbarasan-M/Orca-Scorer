import React, { useState } from 'react';
import PlayerStatsModal from './PlayerStatsModal';

export default function ScorecardView({ scorecard, matchScorecard }) {
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);

  // If matchScorecard has innings, default to viewing the latest innings
  const inningsList = matchScorecard?.innings || (scorecard ? [scorecard] : []);
  const [selectedInningsIdx, setSelectedInningsIdx] = useState(
    inningsList.length > 0 ? inningsList.length - 1 : 0
  );

  const activeInnings = inningsList[selectedInningsIdx] || scorecard;

  if (!activeInnings) return <div className="loading">Loading scorecard...</div>;

  const {
    batting = [],
    bowling = [],
    extras = {},
    total_runs,
    wickets_lost,
    overs,
    run_rate,
    fall_of_wickets = [],
    current_partnership,
    batting_team,
    bowling_team,
  } = activeInnings;

  return (
    <div className="scorecard-container">
      {/* Match Outcome / Status Banner */}
      {matchScorecard?.summary_text && (
        <div className="match-summary-banner">
          <span>🏆 {matchScorecard.summary_text}</span>
        </div>
      )}

      {/* Multiple Innings Selector */}
      {inningsList.length > 1 && (
        <div className="innings-selector-tabs">
          {inningsList.map((inn, idx) => (
            <button
              key={inn.innings_id}
              type="button"
              className={`innings-tab ${selectedInningsIdx === idx ? 'active' : ''}`}
              onClick={() => setSelectedInningsIdx(idx)}
            >
              <span className="tab-team">{inn.batting_team?.short_name || `Innings ${idx + 1}`}</span>
              <span className="tab-score">
                {inn.total_runs}/{inn.wickets_lost} ({inn.overs} ov)
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Innings Card Header */}
      <div className="card-header">
        <div>
          <h3>
            📊 {batting_team?.name || 'Batting'} Innings
          </h3>
          <span className="sub-text">vs {bowling_team?.name || 'Bowling'}</span>
        </div>
        <span className="summary-badge">
          {total_runs}/{wickets_lost} ({overs} ov, RR: {run_rate})
        </span>
      </div>

      {/* Batting Table */}
      <div className="table-responsive">
        <h4>Batting</h4>
        <table className="score-table">
          <thead>
            <tr>
              <th className="text-left">Batter</th>
              <th className="text-left">Dismissal</th>
              <th>R</th>
              <th>B</th>
              <th>4s</th>
              <th>6s</th>
              <th>SR</th>
            </tr>
          </thead>
          <tbody>
            {batting.map((b) => (
              <tr key={b.player_id}>
                <td className="text-left font-bold">
                  <button
                    type="button"
                    className="player-name-link"
                    title="View career stats"
                    onClick={() => setSelectedPlayerId(b.player_id)}
                  >
                    {b.player_name}
                  </button>
                </td>
                <td className="text-left dismissal-cell">{b.dismissal_text}</td>
                <td className="font-bold">{b.runs}</td>
                <td>{b.balls_faced}</td>
                <td>{b.fours}</td>
                <td>{b.sixes}</td>
                <td>{b.strike_rate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Extras Summary */}
      <div className="extras-box">
        <span>
          <strong>Extras:</strong> {extras.total || 0} (b {extras.byes || 0}, lb {extras.leg_byes || 0}, w {extras.wides || 0}, nb {extras.no_balls || 0})
        </span>
      </div>

      {/* Fall of Wickets */}
      {fall_of_wickets && fall_of_wickets.length > 0 && (
        <div className="fow-box">
          <div className="fow-title">Fall of Wickets</div>
          <div className="fow-list">
            {fall_of_wickets.map((f, i) => (
              <span key={f.wicket_number} className="fow-item">
                <strong>{f.score}-{f.wicket_number}</strong> (
                <button
                  type="button"
                  className="player-name-link-inline"
                  onClick={() => setSelectedPlayerId(f.player_id)}
                >
                  {f.player_name}
                </button>
                , {f.overs} ov)
                {i < fall_of_wickets.length - 1 && <span className="fow-sep">, </span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Active Partnership */}
      {current_partnership && (
        <div className="partnership-summary-box">
          <span className="partnership-title">🤝 Active Partnership:</span>
          <span className="partnership-value">
            <strong>{current_partnership.runs}</strong> runs ({current_partnership.balls} balls)
          </span>
          {current_partnership.batter1 && current_partnership.batter2 && (
            <span className="partnership-players">
              — {current_partnership.batter1.player_name}: {current_partnership.batter1.runs} ({current_partnership.batter1.balls}), {current_partnership.batter2.player_name}: {current_partnership.batter2.runs} ({current_partnership.batter2.balls})
            </span>
          )}
        </div>
      )}

      {/* Bowling Table */}
      <div className="table-responsive">
        <h4>Bowling</h4>
        <table className="score-table">
          <thead>
            <tr>
              <th className="text-left">Bowler</th>
              <th>O</th>
              <th>M</th>
              <th>R</th>
              <th>W</th>
              <th>ECON</th>
              <th>Dots</th>
            </tr>
          </thead>
          <tbody>
            {bowling.map((bw) => (
              <tr key={bw.player_id}>
                <td className="text-left font-bold">
                  <button
                    type="button"
                    className="player-name-link"
                    title="View career stats"
                    onClick={() => setSelectedPlayerId(bw.player_id)}
                  >
                    {bw.player_name}
                  </button>
                </td>
                <td>{bw.overs}</td>
                <td>{bw.maidens}</td>
                <td>{bw.runs_conceded}</td>
                <td className="font-bold text-wicket">{bw.wickets}</td>
                <td>{bw.economy_rate}</td>
                <td>{bw.dots}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Player Career Stats Modal */}
      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  );
}
