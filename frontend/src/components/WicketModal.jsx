import React, { useState } from 'react';

const FIELDER_REQUIRED_TYPES = ['CAUGHT', 'STUMPED', 'RUN_OUT'];

export default function WicketModal({
  isOpen,
  onClose,
  onConfirm,
  strikerId,
  nonStrikerId,
  battingSquad,
  fieldingSquad,
}) {
  const [wicketType, setWicketType] = useState('CAUGHT');
  const [playerOutId, setPlayerOutId] = useState(strikerId);
  const [fielderId, setFielderId] = useState('');
  const [runsOffBat, setRunsOffBat] = useState(0);

  if (!isOpen) return null;

  const requiresFielder = FIELDER_REQUIRED_TYPES.includes(wicketType);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (requiresFielder && !fielderId) {
      alert(`Please select the fielder for ${wicketType}`);
      return;
    }

    onConfirm({
      wicket_type: wicketType,
      player_out_id: Number(playerOutId),
      fielder_id: requiresFielder ? Number(fielderId) : null,
      runs_off_bat: Number(runsOffBat),
    });
    onClose();
  };

  const getPlayerName = (id) => {
    const p = battingSquad.find((b) => b.player_id === id);
    return p?.player?.name || `Player #${id}`;
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>⚡ Record Dismissal</h3>
          <button type="button" className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Dismissal Type</label>
            <select
              value={wicketType}
              onChange={(e) => {
                setWicketType(e.target.value);
                if (!FIELDER_REQUIRED_TYPES.includes(e.target.value)) {
                  setFielderId('');
                }
              }}
            >
              <option value="CAUGHT">Caught</option>
              <option value="BOWLED">Bowled</option>
              <option value="LBW">LBW</option>
              <option value="RUN_OUT">Run Out</option>
              <option value="STUMPED">Stumped</option>
              <option value="HIT_WICKET">Hit Wicket</option>
              <option value="RETIRED_HURT">Retired Hurt</option>
              <option value="RETIRED_OUT">Retired Out</option>
            </select>
          </div>

          <div className="form-group">
            <label>Batter Out</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  name="batter_out"
                  value={strikerId}
                  checked={playerOutId === strikerId}
                  onChange={() => setPlayerOutId(strikerId)}
                />
                Striker: {getPlayerName(strikerId)}
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="batter_out"
                  value={nonStrikerId}
                  checked={playerOutId === nonStrikerId}
                  onChange={() => setPlayerOutId(nonStrikerId)}
                />
                Non-Striker: {getPlayerName(nonStrikerId)}
              </label>
            </div>
          </div>

          {requiresFielder && (
            <div className="form-group">
              <label>Fielder (Catcher / Stumper / Thrower) *</label>
              <select
                value={fielderId}
                onChange={(e) => setFielderId(e.target.value)}
                required
              >
                <option value="">Select Fielder...</option>
                {fieldingSquad.map((f) => (
                  <option key={f.player_id} value={f.player_id}>
                    {f.player?.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {wicketType === 'RUN_OUT' && (
            <div className="form-group">
              <label>Runs Completed Before Run Out</label>
              <select
                value={runsOffBat}
                onChange={(e) => setRunsOffBat(Number(e.target.value))}
              >
                <option value={0}>0 (No runs completed)</option>
                <option value={1}>1 Run</option>
                <option value={2}>2 Runs</option>
                <option value={3}>3 Runs</option>
              </select>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-danger">
              Confirm Wicket
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
