import React, { useState } from 'react';

export default function ScoringKeypad({
  onScoreBall,
  onOpenWicketModal,
  onUndoLastBall,
  isOverComplete,
  disabled,
}) {
  const [extraMode, setExtraMode] = useState(null); // 'WIDE', 'NO_BALL', 'BYE', 'LEG_BYE'
  const [commentary, setCommentary] = useState('');

  const handleRunTap = (runs) => {
    let payload = {
      runs_off_bat: 0,
      wide_runs: 0,
      no_ball_runs: 0,
      bye_runs: 0,
      leg_bye_runs: 0,
      penalty_runs: 0,
      commentary: commentary.trim() || null,
    };

    if (!extraMode) {
      payload.runs_off_bat = runs;
    } else if (extraMode === 'WIDE') {
      // 1 penalty wide + any additional runs running
      payload.wide_runs = 1 + runs;
    } else if (extraMode === 'NO_BALL') {
      payload.no_ball_runs = 1;
      payload.runs_off_bat = runs;
    } else if (extraMode === 'BYE') {
      payload.bye_runs = runs;
    } else if (extraMode === 'LEG_BYE') {
      payload.leg_bye_runs = runs;
    }

    onScoreBall(payload);
    setExtraMode(null);
    setCommentary('');
  };

  return (
    <div className="keypad-wrapper">
      {/* Active Extra Mode indicator */}
      {extraMode && (
        <div className="extra-active-bar">
          <span>
            Scoring <strong>{extraMode}</strong>: Tap runs conceded on this ball
          </span>
          <button
            type="button"
            className="btn-cancel-extra"
            onClick={() => setExtraMode(null)}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Main Runs Grid */}
      <div className="runs-grid">
        <button
          type="button"
          className="key-btn key-dot"
          disabled={disabled}
          onClick={() => handleRunTap(0)}
        >
          <span className="key-main">0</span>
          <span className="key-sub">Dot</span>
        </button>

        <button
          type="button"
          className="key-btn key-run"
          disabled={disabled}
          onClick={() => handleRunTap(1)}
        >
          <span className="key-main">1</span>
          <span className="key-sub">Single</span>
        </button>

        <button
          type="button"
          className="key-btn key-run"
          disabled={disabled}
          onClick={() => handleRunTap(2)}
        >
          <span className="key-main">2</span>
          <span className="key-sub">Two</span>
        </button>

        <button
          type="button"
          className="key-btn key-run"
          disabled={disabled}
          onClick={() => handleRunTap(3)}
        >
          <span className="key-main">3</span>
          <span className="key-sub">Three</span>
        </button>

        <button
          type="button"
          className="key-btn key-four"
          disabled={disabled}
          onClick={() => handleRunTap(4)}
        >
          <span className="key-main">4</span>
          <span className="key-sub">FOUR</span>
        </button>

        <button
          type="button"
          className="key-btn key-six"
          disabled={disabled}
          onClick={() => handleRunTap(6)}
        >
          <span className="key-main">6</span>
          <span className="key-sub">SIX</span>
        </button>
      </div>

      {/* Extras & Wicket Controls */}
      <div className="action-row">
        <button
          type="button"
          className={`btn-action ${extraMode === 'WIDE' ? 'btn-active' : ''}`}
          disabled={disabled}
          onClick={() => setExtraMode(extraMode === 'WIDE' ? null : 'WIDE')}
        >
          Wide
        </button>

        <button
          type="button"
          className={`btn-action ${extraMode === 'NO_BALL' ? 'btn-active' : ''}`}
          disabled={disabled}
          onClick={() => setExtraMode(extraMode === 'NO_BALL' ? null : 'NO_BALL')}
        >
          No Ball
        </button>

        <button
          type="button"
          className={`btn-action ${extraMode === 'LEG_BYE' ? 'btn-active' : ''}`}
          disabled={disabled}
          onClick={() => setExtraMode(extraMode === 'LEG_BYE' ? null : 'LEG_BYE')}
        >
          Leg Bye
        </button>

        <button
          type="button"
          className={`btn-action ${extraMode === 'BYE' ? 'btn-active' : ''}`}
          disabled={disabled}
          onClick={() => setExtraMode(extraMode === 'BYE' ? null : 'BYE')}
        >
          Bye
        </button>

        <button
          type="button"
          className="btn-action btn-wicket"
          disabled={disabled}
          onClick={onOpenWicketModal}
        >
          Wicket
        </button>
      </div>

      {/* Commentary & Undo */}
      <div className="footer-controls">
        <input
          type="text"
          className="commentary-input"
          placeholder="Ball commentary / note (optional)..."
          value={commentary}
          onChange={(e) => setCommentary(e.target.value)}
        />
        <button
          type="button"
          className="btn-undo"
          onClick={onUndoLastBall}
          title="Delete previous delivery"
        >
          ↩ Undo Ball
        </button>
      </div>
    </div>
  );
}
