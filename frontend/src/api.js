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
  // Matches
  getMatches: async () => {
    const res = await fetch('/matches?limit=20');
    return handleResponse(res);
  },

  getMatch: async (matchId) => {
    const res = await fetch(`/matches/${matchId}`);
    return handleResponse(res);
  },

  getMatchPlayers: async (matchId, teamId) => {
    const url = teamId
      ? `/matches/${matchId}/players?team_id=${teamId}`
      : `/matches/${matchId}/players`;
    const res = await fetch(url);
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
