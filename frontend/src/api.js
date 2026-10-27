/**
 * API client communicating with the FastAPI backend.
 * Uses relative paths thanks to the Vite proxy configured in vite.config.js.
 */

async function handleResponse(res) {
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const message = errorData.detail || `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  // Teams
  getTeams: async () => {
    const res = await fetch('/teams?limit=50');
    return handleResponse(res);
  },

  createTeam: async (payload) => {
    const res = await fetch('/teams', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  getTeamSquad: async (teamId) => {
    const res = await fetch(`/teams/${teamId}/squad`);
    return handleResponse(res);
  },

  addPlayerToSquad: async (teamId, playerId) => {
    const res = await fetch(`/teams/${teamId}/squad`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: playerId }),
    });
    return handleResponse(res);
  },

  // Players
  getPlayers: async () => {
    const res = await fetch('/players?limit=100');
    return handleResponse(res);
  },

  createPlayer: async (payload) => {
    const res = await fetch('/players', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  getPlayerStatistics: async (playerId) => {
    const res = await fetch(`/players/${playerId}/statistics`);
    return handleResponse(res);
  },

  // Matches
  getMatches: async () => {
    const res = await fetch('/matches?limit=50');
    return handleResponse(res);
  },

  getMatch: async (matchId) => {
    const res = await fetch(`/matches/${matchId}`);
    return handleResponse(res);
  },

  createMatch: async (payload) => {
    const res = await fetch('/matches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  updateMatch: async (matchId, payload) => {
    const res = await fetch(`/matches/${matchId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  getMatchPlayers: async (matchId, teamId) => {
    const url = teamId
      ? `/matches/${matchId}/players?team_id=${teamId}`
      : `/matches/${matchId}/players`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  setMatchSquad: async (matchId, payload) => {
    const res = await fetch(`/matches/${matchId}/players`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  getMatchScorecard: async (matchId) => {
    const res = await fetch(`/matches/${matchId}/scorecard`);
    return handleResponse(res);
  },

  // Innings
  getInnings: async (inningsId) => {
    const res = await fetch(`/innings/${inningsId}`);
    return handleResponse(res);
  },

  createInnings: async (payload) => {
    const res = await fetch('/innings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  startNextInnings: async (matchId) => {
    const res = await fetch(`/matches/${matchId}/innings/next`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  getInningsDeliveries: async (inningsId) => {
    const res = await fetch(`/innings/${inningsId}/deliveries?limit=300`);
    return handleResponse(res);
  },

  getInningsScorecard: async (inningsId) => {
    const res = await fetch(`/innings/${inningsId}/scorecard`);
    return handleResponse(res);
  },

  // Scoring
  recordDelivery: async (inningsId, payload) => {
    const res = await fetch(`/innings/${inningsId}/deliveries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  undoLastDelivery: async (inningsId) => {
    const res = await fetch(`/innings/${inningsId}/deliveries/last`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },
};
