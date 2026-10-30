import React, { useEffect, useState } from 'react';
import { api } from '../api';
import PlayerStatsModal from './PlayerStatsModal';

const PLAYER_ROLES = [
  'BATTER',
  'BOWLER',
  'ALL_ROUNDER',
  'WICKET_KEEPER',
  'WICKET_KEEPER_BATTER',
];

export default function TeamsPlayersView() {
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [squad, setSquad] = useState([]);

  // New Team Form state
  const [showNewTeamModal, setShowNewTeamModal] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamShortName, setNewTeamShortName] = useState('');

  // Add Player Form state
  const [showNewPlayerModal, setShowNewPlayerModal] = useState(false);
  const [newPlayerName, setNewPlayerName] = useState('');
  const [newPlayerRole, setNewPlayerRole] = useState('ALL_ROUNDER');

  // Player Stats modal
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load all teams
  const loadTeams = async () => {
    try {
      setLoading(true);
      const data = await api.getTeams();
      setTeams(data);
      if (data.length > 0 && !selectedTeam) {
        setSelectedTeam(data[0]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeams();
  }, []);

  // Load squad when selected team changes
  useEffect(() => {
    if (!selectedTeam) return;
    async function loadSquad() {
      try {
        const sq = await api.getTeamSquad(selectedTeam.id);
        setSquad(sq);
      } catch (err) {
        setError(err.message);
      }
    }
    loadSquad();
  }, [selectedTeam]);

  // Handle Team Creation
  const handleCreateTeam = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      const created = await api.createTeam({
        name: newTeamName.trim(),
        short_name: newTeamShortName.trim().toUpperCase(),
      });
      setShowNewTeamModal(false);
      setNewTeamName('');
      setNewTeamShortName('');
      await loadTeams();
      setSelectedTeam(created);
    } catch (err) {
      setError(err.message);
    }
  };

  // Handle Player Creation + Squad Addition
  const handleAddPlayer = async (e) => {
    e.preventDefault();
    if (!selectedTeam) return;

    try {
      setError(null);
      // 1. Create player
      const player = await api.createPlayer({
        name: newPlayerName.trim(),
        player_role: newPlayerRole,
      });

      // 2. Add to team squad
      await api.addPlayerToSquad(selectedTeam.id, player.id);

      setShowNewPlayerModal(false);
      setNewPlayerName('');
      setNewPlayerRole('ALL_ROUNDER');

      // Refresh squad
      const sq = await api.getTeamSquad(selectedTeam.id);
      setSquad(sq);
    } catch (err) {
      setError(err.message);
    }
  };

  // View Player Career Stats
  const handleViewStats = (playerId) => {
    setSelectedPlayerId(playerId);
  };

  return (
    <div className="teams-players-container">
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button type="button" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="teams-grid-layout">
        {/* Left Column: Teams List */}
        <div className="teams-sidebar">
          <div className="section-header">
            <h3>Teams</h3>
            <button
              type="button"
              className="btn btn-primary-sm"
              onClick={() => setShowNewTeamModal(true)}
            >
              + New Team
            </button>
          </div>

          <div className="teams-list">
            {teams.map((t) => (
              <div
                key={t.id}
                className={`team-item ${selectedTeam?.id === t.id ? 'active' : ''}`}
                onClick={() => setSelectedTeam(t)}
              >
                <span className="team-badge">{t.short_name}</span>
                <span className="team-name">{t.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Squad Roster */}
        <div className="squad-panel">
          {selectedTeam ? (
            <>
              <div className="section-header">
                <div>
                  <h3>{selectedTeam.name} ({selectedTeam.short_name}) Squad</h3>
                  <span className="sub-text">{squad.length} Active Players</span>
                </div>
                <button
                  type="button"
                  className="btn btn-primary-sm"
                  onClick={() => setShowNewPlayerModal(true)}
                >
                  + Add Player
                </button>
              </div>

              {squad.length === 0 ? (
                <div className="empty-panel">
                  <p>No players in this squad yet. Click "+ Add Player" to register players.</p>
                </div>
              ) : (
                <div className="squad-table-wrapper">
                  <table className="score-table">
                    <thead>
                      <tr>
                        <th className="text-left">#</th>
                        <th className="text-left">Player Name</th>
                        <th className="text-left">Role</th>
                        <th>Joined</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {squad.map((p, index) => (
                        <tr key={p.id}>
                          <td className="text-left">{index + 1}</td>
                          <td className="text-left font-bold">{p.name}</td>
                          <td className="text-left">
                            <span className="role-tag">{p.player_role.replace(/_/g, ' ')}</span>
                          </td>
                          <td>{p.joined_at}</td>
                          <td>
                            <button
                              type="button"
                              className="btn-link"
                              onClick={() => handleViewStats(p.id)}
                            >
                              Career Stats
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <div className="empty-panel">Select or create a team</div>
          )}
        </div>
      </div>

      {/* New Team Modal */}
      {showNewTeamModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Create New Team</h3>
              <button type="button" className="close-btn" onClick={() => setShowNewTeamModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateTeam} className="modal-form">
              <div className="form-group">
                <label>Team Full Name *</label>
                <input
                  type="text"
                  placeholder="e.g. Chennai Super Kings"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Short Name (2-5 letters) *</label>
                <input
                  type="text"
                  placeholder="e.g. CSK"
                  maxLength={5}
                  value={newTeamShortName}
                  onChange={(e) => setNewTeamShortName(e.target.value.toUpperCase())}
                  required
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowNewTeamModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-brand">
                  Create Team
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Player Modal */}
      {showNewPlayerModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Add Player to {selectedTeam?.name}</h3>
              <button type="button" className="close-btn" onClick={() => setShowNewPlayerModal(false)}>✕</button>
            </div>
            <form onSubmit={handleAddPlayer} className="modal-form">
              <div className="form-group">
                <label>Player Name *</label>
                <input
                  type="text"
                  placeholder="e.g. MS Dhoni"
                  value={newPlayerName}
                  onChange={(e) => setNewPlayerName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Player Role *</label>
                <select
                  value={newPlayerRole}
                  onChange={(e) => setNewPlayerRole(e.target.value)}
                >
                  {PLAYER_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {role.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowNewPlayerModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-brand">
                  Add to Squad
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Player Stats Modal */}
      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  );
}
