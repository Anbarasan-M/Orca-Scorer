import React, { useEffect, useState } from 'react';
import { api } from '../api';

const MATCH_FORMATS = ['T20', 'ODI', 'T10', 'CUSTOM', 'TEST'];

export default function NewMatchModal({ isOpen, onClose, onMatchCreated }) {
  const [teams, setTeams] = useState([]);
  const [team1Id, setTeam1Id] = useState('');
  const [team2Id, setTeam2Id] = useState('');
  const [format, setFormat] = useState('T20');
  const [totalOvers, setTotalOvers] = useState(20);
  const [venue, setVenue] = useState('Local Grounds');

  const [tossWinnerId, setTossWinnerId] = useState('');
  const [tossDecision, setTossDecision] = useState('BAT');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    async function load() {
      try {
        const teamList = await api.getTeams();
        setTeams(teamList);
        if (teamList.length >= 2) {
          setTeam1Id(teamList[0].id);
          setTeam2Id(teamList[1].id);
          setTossWinnerId(teamList[0].id);
        }
      } catch (err) {
        setError(err.message);
      }
    }
    load();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFormatChange = (fmt) => {
    setFormat(fmt);
    if (fmt === 'T20') setTotalOvers(20);
    else if (fmt === 'ODI') setTotalOvers(50);
    else if (fmt === 'T10') setTotalOvers(10);
    else if (fmt === 'TEST') setTotalOvers('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (team1Id === team2Id) {
      setError('Team 1 and Team 2 must be different teams');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      // 1. Create Match
      const matchPayload = {
        team1_id: Number(team1Id),
        team2_id: Number(team2Id),
        match_date: new Date().toISOString(),
        venue: venue.trim(),
        format: format,
        total_overs: format === 'TEST' ? null : Number(totalOvers),
      };
      const createdMatch = await api.createMatch(matchPayload);

      // 2. Record Toss
      const selectedTossWinner = Number(tossWinnerId || team1Id);
      await api.updateMatch(createdMatch.id, {
        toss_winner_id: selectedTossWinner,
        toss_decision: tossDecision,
        status: 'LIVE',
      });

      // 3. Automatically Nominate Match Players from Active Squads
      const [t1Squad, t2Squad] = await Promise.all([
        api.getTeamSquad(team1Id),
        api.getTeamSquad(team2Id),
      ]);

      if (t1Squad.length > 0) {
        await api.setMatchSquad(createdMatch.id, {
          team_id: Number(team1Id),
          players: t1Squad.map((p, idx) => ({
            player_id: p.id,
            batting_position: idx + 1,
            is_captain: idx === 0,
            is_wicket_keeper: idx === 1,
            is_substitute: false,
          })),
        });
      }

      if (t2Squad.length > 0) {
        await api.setMatchSquad(createdMatch.id, {
          team_id: Number(team2Id),
          players: t2Squad.map((p, idx) => ({
            player_id: p.id,
            batting_position: idx + 1,
            is_captain: idx === 0,
            is_wicket_keeper: idx === 1,
            is_substitute: false,
          })),
        });
      }

      // 4. Start Innings 1 based on Toss
      // If toss winner chose BAT, they bat first; otherwise the other team bats first
      let battingTeamId, bowlingTeamId;
      if (tossDecision === 'BAT') {
        battingTeamId = selectedTossWinner;
        bowlingTeamId = selectedTossWinner === Number(team1Id) ? Number(team2Id) : Number(team1Id);
      } else {
        bowlingTeamId = selectedTossWinner;
        battingTeamId = selectedTossWinner === Number(team1Id) ? Number(team2Id) : Number(team1Id);
      }

      await api.createInnings({
        match_id: createdMatch.id,
        innings_number: 1,
        batting_team_id: battingTeamId,
        bowling_team_id: bowlingTeamId,
        max_overs: format === 'TEST' ? null : Number(totalOvers),
      });

      onMatchCreated(createdMatch.id);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>⚡ Schedule & Start New Match</h3>
          <button type="button" className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && <div className="error-banner"><span>⚠️ {error}</span></div>}

        {teams.length < 2 ? (
          <div className="empty-panel">
            <p>You need at least 2 teams to schedule a match.</p>
            <p>Please create teams under the "Teams & Players" tab first.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="modal-form">
            <div className="form-row">
              <div className="form-group flex-1">
                <label>Team 1 *</label>
                <select
                  value={team1Id}
                  onChange={(e) => setTeam1Id(e.target.value)}
                  required
                >
                  {teams.map((t) => (
                    <option key={t.id} value={t.id} disabled={t.id === Number(team2Id)}>
                      {t.name} ({t.short_name})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group flex-1">
                <label>Team 2 *</label>
                <select
                  value={team2Id}
                  onChange={(e) => setTeam2Id(e.target.value)}
                  required
                >
                  {teams.map((t) => (
                    <option key={t.id} value={t.id} disabled={t.id === Number(team1Id)}>
                      {t.name} ({t.short_name})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Format</label>
                <select value={format} onChange={(e) => handleFormatChange(e.target.value)}>
                  {MATCH_FORMATS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>

              {format !== 'TEST' && (
                <div className="form-group flex-1">
                  <label>Overs Per Innings</label>
                  <input
                    type="number"
                    min="1"
                    max="200"
                    value={totalOvers}
                    onChange={(e) => setTotalOvers(e.target.value)}
                    required
                  />
                </div>
              )}
            </div>

            <div className="form-group">
              <label>Venue</label>
              <input
                type="text"
                placeholder="e.g. M.A. Chidambaram Stadium"
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
              />
            </div>

            <div className="divider" />

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Toss Winner</label>
                <select
                  value={tossWinnerId}
                  onChange={(e) => setTossWinnerId(e.target.value)}
                >
                  <option value={team1Id}>
                    {teams.find((t) => t.id === Number(team1Id))?.name || 'Team 1'}
                  </option>
                  <option value={team2Id}>
                    {teams.find((t) => t.id === Number(team2Id))?.name || 'Team 2'}
                  </option>
                </select>
              </div>

              <div className="form-group flex-1">
                <label>Elected To</label>
                <select
                  value={tossDecision}
                  onChange={(e) => setTossDecision(e.target.value)}
                >
                  <option value="BAT">BAT</option>
                  <option value="BOWL">BOWL</option>
                </select>
              </div>
            </div>

            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn-brand" disabled={submitting}>
                {submitting ? 'Starting Match...' : 'Start Match & Score'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
