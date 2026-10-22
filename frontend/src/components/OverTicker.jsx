import React from 'react';

function getBallBadge(delivery) {
  if (delivery.wickets && delivery.wickets.length > 0) {
    return { text: 'W', className: 'ball-wicket' };
  }
  if (delivery.wide_runs > 0) {
    return {
      text: delivery.wide_runs === 1 ? 'Wd' : `${delivery.wide_runs}Wd`,
      className: 'ball-extra',
    };
  }
  if (delivery.no_ball_runs > 0) {
    const total = delivery.no_ball_runs + delivery.runs_off_bat;
    return { text: `${total}Nb`, className: 'ball-extra' };
  }
  if (delivery.leg_bye_runs > 0) {
    return { text: `${delivery.leg_bye_runs}lb`, className: 'ball-extra' };
  }
  if (delivery.bye_runs > 0) {
    return { text: `${delivery.bye_runs}b`, className: 'ball-extra' };
  }
  if (delivery.runs_off_bat === 6) {
    return { text: '6', className: 'ball-six' };
  }
  if (delivery.runs_off_bat === 4) {
    return { text: '4', className: 'ball-four' };
  }
  if (delivery.runs_off_bat === 0) {
    return { text: '•', className: 'ball-dot' };
  }
  return { text: String(delivery.runs_off_bat), className: 'ball-run' };
}

export default function OverTicker({ deliveries }) {
  if (!deliveries || deliveries.length === 0) {
    return (
      <div className="over-ticker">
        <span className="ticker-label">This Over:</span>
        <span className="no-balls-yet">No balls bowled in this over</span>
      </div>
    );
  }

  // Get current over number from the latest delivery
  const latestDelivery = deliveries[deliveries.length - 1];
  const currentOverNum = latestDelivery.over_number;

  // Filter deliveries belonging to this current over
  const thisOverDeliveries = deliveries.filter(
    (d) => d.over_number === currentOverNum
  );

  return (
    <div className="over-ticker">
      <span className="ticker-label">Over {currentOverNum}:</span>
      <div className="balls-row">
        {thisOverDeliveries.map((delivery) => {
          const badge = getBallBadge(delivery);
          return (
            <div
              key={delivery.id || delivery.ball_seq}
              className={`ball-pill ${badge.className}`}
              title={`Ball ${delivery.over_number}.${delivery.ball_number} - ${delivery.total_runs} runs`}
            >
              {badge.text}
            </div>
          );
        })}
      </div>
    </div>
  );
}
