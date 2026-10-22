import React from 'react';

export default function ScorecardView({ scorecard }) {
  if (!scorecard) return <div className="loading">Loading scorecard...</div>;

  const { batting = [], bowling = [], extras = {}, total_runs, wickets_lost, overs, run_rate } = scorecard;

  return (
    <div className="scorecard-container">
      <div className="card-header">
        <h3>📊 Innings Scorecard</h3>
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
                <td className="text-left font-bold">{b.player_name}</td>
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
                <td className="text-left font-bold">{bw.player_name}</td>
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
    </div>
  );
}
