import React, { useEffect, useState } from 'react';
import { api } from '../api';

export default function PlayerStatsModal({ playerId, onClose }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!playerId) {
      setStats(null);
      return;
    }

    let isMounted = true;
    async function loadStats() {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getPlayerStatistics(playerId);
        if (isMounted) setStats(data);
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadStats();
    return () => {
      isMounted = false;
    };
  }, [playerId]);

  if (!playerId) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            📈 {stats ? `${stats.player_name} — Career Stats` : 'Player Statistics'}
          </h3>
          <button type="button" className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {loading && <div className="loading" style={{ padding: '24px 0' }}>Loading statistics...</div>}

        {error && (
          <div className="error-banner" style={{ margin: '12px 0' }}>
            <span>⚠️ {error}</span>
          </div>
        )}

        {stats && !loading && (
          <div className="stats-breakdown">
            {/* Batting Section */}
            <div className="stats-section">
              <h4>Batting</h4>
              <div className="stats-grid">
                <div><span>Innings:</span> <strong>{stats.batting.innings}</strong></div>
                <div><span>Runs:</span> <strong>{stats.batting.runs}</strong></div>
                <div><span>High Score:</span> <strong>{stats.batting.highest_score}</strong></div>
                <div><span>Avg:</span> <strong>{stats.batting.average ?? '-'}</strong></div>
                <div><span>SR:</span> <strong>{stats.batting.strike_rate}</strong></div>
                <div><span>4s / 6s:</span> <strong>{stats.batting.fours} / {stats.batting.sixes}</strong></div>
                <div><span>50s / 100s:</span> <strong>{stats.batting.fifties} / {stats.batting.hundreds}</strong></div>
                <div><span>Ducks:</span> <strong>{stats.batting.ducks}</strong></div>
              </div>
            </div>

            {/* Bowling Section */}
            <div className="stats-section">
              <h4>Bowling</h4>
              <div className="stats-grid">
                <div><span>Overs:</span> <strong>{stats.bowling.overs}</strong></div>
                <div><span>Wickets:</span> <strong>{stats.bowling.wickets}</strong></div>
                <div><span>Runs Conceded:</span> <strong>{stats.bowling.runs_conceded}</strong></div>
                <div><span>Economy:</span> <strong>{stats.bowling.economy_rate}</strong></div>
                <div><span>Avg:</span> <strong>{stats.bowling.average ?? '-'}</strong></div>
                <div><span>SR:</span> <strong>{stats.bowling.strike_rate ?? '-'}</strong></div>
                <div><span>Best:</span> <strong>{stats.bowling.best_bowling ?? '-'}</strong></div>
                <div><span>4w / 5w:</span> <strong>{stats.bowling.four_wickets} / {stats.bowling.five_wickets}</strong></div>
              </div>
            </div>

            {/* Fielding Section */}
            <div className="stats-section">
              <h4>Fielding</h4>
              <div className="stats-grid">
                <div><span>Catches:</span> <strong>{stats.fielding.catches}</strong></div>
                <div><span>Run Outs:</span> <strong>{stats.fielding.run_outs}</strong></div>
                <div><span>Stumpings:</span> <strong>{stats.fielding.stumpings}</strong></div>
              </div>
            </div>
          </div>
        )}

        <div className="modal-actions" style={{ marginTop: '16px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
