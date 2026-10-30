import React, { useEffect, useState } from 'react';
import { api } from './api';
import ScoreBanner from './components/ScoreBanner';
import BattersBowlerHUD from './components/BattersBowlerHUD';
import OverTicker from './components/OverTicker';
import ScoringKeypad from './components/ScoringKeypad';
import WicketModal from './components/WicketModal';
import ScorecardView from './components/ScorecardView';
import TeamsPlayersView from './components/TeamsPlayersView';
import NewMatchModal from './components/NewMatchModal';
import './App.css';

export default function App() {
  const [matches, setMatches] = useState([]);
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [match, setMatch] = useState(null);
  const [innings, setInnings] = useState(null);
  const [scorecard, setScorecard] = useState(null);
  const [matchScorecard, setMatchScorecard] = useState(null);
  const [matchSummary, setMatchSummary] = useState(null);
  const [deliveries, setDeliveries] = useState([]);

  const [battingSquad, setBattingSquad] = useState([]);
  const [fieldingSquad, setFieldingSquad] = useState([]);

  const [strikerId, setStrikerId] = useState(null);
  const [nonStrikerId, setNonStrikerId] = useState(null);
  const [bowlerId, setBowlerId] = useState(null);

  const [isOverComplete, setIsOverComplete] = useState(false);
  const [isWicketModalOpen, setIsWicketModalOpen] = useState(false);
  const [isNewMatchModalOpen, setIsNewMatchModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('scoring'); // 'scoring' | 'scorecard' | 'teams'
  const [theme, setTheme] = useState(() => localStorage.getItem('orca_theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('orca_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 1. Initial Load: Fetch matches
  const loadMatches = async () => {
    try {
      setLoading(true);
      const matchData = await api.getMatches();
      setMatches(matchData);
      if (matchData.length > 0 && !selectedMatchId) {
        setSelectedMatchId(matchData[0].id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatches();
  }, []);

  // 2. Load Selected Match, Innings, Players, and Deliveries
  useEffect(() => {
    if (!selectedMatchId) return;

    async function loadMatchDetails() {
      try {
        setLoading(true);
        setError(null);

        // Fetch match details
        const m = await api.getMatch(selectedMatchId);
        setMatch(m);

        // Check for innings (fetch 1st innings or latest)
        let inn = null;
        try {
          const mScorecard = await api.getMatchScorecard(selectedMatchId);
          setMatchScorecard(mScorecard);
          setMatchSummary(mScorecard.summary_text);
          if (mScorecard.innings && mScorecard.innings.length > 0) {
            const latestInnId = mScorecard.innings[mScorecard.innings.length - 1].innings_id;
            inn = await api.getInnings(latestInnId);
          }
        } catch {
          // Innings may not exist yet
        }
        setInnings(inn);

        if (inn) {
          // Fetch batting & fielding squads
          const batPlayers = await api.getMatchPlayers(selectedMatchId, inn.batting_team_id);
          const fieldPlayers = await api.getMatchPlayers(selectedMatchId, inn.bowling_team_id);
          setBattingSquad(batPlayers);
          setFieldingSquad(fieldPlayers);

          // Fetch deliveries and scorecard
          const delivs = await api.getInningsDeliveries(inn.id);
          setDeliveries(delivs);

          const sc = await api.getInningsScorecard(inn.id);
          setScorecard(sc);

          // Auto-select initial batters & bowler if not set
          if (delivs.length > 0) {
            const last = delivs[delivs.length - 1];
            setStrikerId(last.batter_id);
            setNonStrikerId(last.non_striker_id);
            setBowlerId(last.bowler_id);
          } else {
            if (batPlayers.length >= 2) {
              setStrikerId(batPlayers[0].player_id);
              setNonStrikerId(batPlayers[1].player_id);
            }
            if (fieldPlayers.length >= 1) {
              setBowlerId(fieldPlayers[0].player_id);
            }
          }
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadMatchDetails();
  }, [selectedMatchId]);

  // Refresh current innings data (scorecard + deliveries)
  const refreshInningsData = async (innId) => {
    try {
      const [sc, delivs, mScorecard, m] = await Promise.all([
        api.getInningsScorecard(innId),
        api.getInningsDeliveries(innId),
        api.getMatchScorecard(selectedMatchId),
        api.getMatch(selectedMatchId),
      ]);
      setScorecard(sc);
      setDeliveries(delivs);
      setMatchScorecard(mScorecard);
      setMatchSummary(mScorecard.summary_text);
      setMatch(m);
    } catch (err) {
      setError(err.message);
    }
  };

  // 3. Score a ball
  const handleScoreBall = async (ballPayload) => {
    if (!innings || !strikerId || !nonStrikerId || !bowlerId) {
      alert('Please select both batters and a bowler before scoring.');
      return;
    }

    try {
      setError(null);
      const payload = {
        batter_id: strikerId,
        non_striker_id: nonStrikerId,
        bowler_id: bowlerId,
        ...ballPayload,
      };

      const res = await api.recordDelivery(innings.id, payload);

      // Apply strike rotation returned by backend scoring engine
      if (res.next_striker_id) setStrikerId(res.next_striker_id);
      if (res.next_non_striker_id) setNonStrikerId(res.next_non_striker_id);
      setIsOverComplete(res.is_over_complete);

      // If the over completed, reset bowler selection so user is prompted to pick a new bowler
      if (res.is_over_complete) {
        setBowlerId(null);
      }

      await refreshInningsData(innings.id);

      // If this delivery completed the innings, refresh the full match
      if (res.is_innings_complete) {
        const updatedInn = await api.getInnings(innings.id);
        setInnings(updatedInn);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // 4. Handle Wicket Confirmation
  const handleWicketConfirm = async (wicketData) => {
    try {
      setError(null);
      const payload = {
        batter_id: strikerId,
        non_striker_id: nonStrikerId,
        bowler_id: bowlerId,
        runs_off_bat: wicketData.runs_off_bat || 0,
        wicket: {
          player_out_id: wicketData.player_out_id,
          wicket_type: wicketData.wicket_type,
          fielder_id: wicketData.fielder_id,
        },
      };

      const res = await api.recordDelivery(innings.id, payload);

      if (res.next_striker_id) setStrikerId(res.next_striker_id);
      if (res.next_non_striker_id) setNonStrikerId(res.next_non_striker_id);
      setIsOverComplete(res.is_over_complete);

      await refreshInningsData(innings.id);

      if (res.is_innings_complete) {
        const updatedInn = await api.getInnings(innings.id);
        setInnings(updatedInn);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // 5. Handle Undo
  const handleUndo = async () => {
    if (!innings) return;
    if (!window.confirm('Are you sure you want to delete the last ball?')) return;

    try {
      setError(null);
      await api.undoLastDelivery(innings.id);
      const updatedInn = await api.getInnings(innings.id);
      setInnings(updatedInn);
      await refreshInningsData(innings.id);
    } catch (err) {
      setError(err.message);
    }
  };

  // 6. Handle New Match Created
  const handleNewMatchCreated = async (newMatchId) => {
    await loadMatches();
    setSelectedMatchId(newMatchId);
    setActiveTab('scoring');
  };

  // 7. Start 2nd Innings
  const handleStartNextInnings = async () => {
    try {
      setLoading(true);
      setError(null);
      const nextInn = await api.startNextInnings(selectedMatchId);
      setInnings(nextInn);

      // Load squads for reversed roles
      const batPlayers = await api.getMatchPlayers(selectedMatchId, nextInn.batting_team_id);
      const fieldPlayers = await api.getMatchPlayers(selectedMatchId, nextInn.bowling_team_id);
      setBattingSquad(batPlayers);
      setFieldingSquad(fieldPlayers);

      if (batPlayers.length >= 2) {
        setStrikerId(batPlayers[0].player_id);
        setNonStrikerId(batPlayers[1].player_id);
      }
      if (fieldPlayers.length >= 1) {
        setBowlerId(fieldPlayers[0].player_id);
      }

      await refreshInningsData(nextInn.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <header className="navbar">
        <div className="brand">
          <span className="brand-icon">🏏</span>
          <span className="brand-title">Orca Scorer</span>
        </div>

        <div className="nav-controls">
          {matches.length > 0 && (
            <label className="match-picker-label">
              Match:
              <select
                value={selectedMatchId || ''}
                onChange={(e) => setSelectedMatchId(Number(e.target.value))}
                className="match-select"
              >
                {matches.map((m) => (
                  <option key={m.id} value={m.id}>
                    #{m.id} {m.team1?.short_name} vs {m.team2?.short_name} ({m.format})
                  </option>
                ))}
              </select>
            </label>
          )}

          <button
            type="button"
            className="btn-theme-toggle"
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            onClick={toggleTheme}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>

          <button
            type="button"
            className="btn btn-new-match"
            onClick={() => setIsNewMatchModalOpen(true)}
          >
            + New Match
          </button>

          <div className="tab-buttons">
            <button
              type="button"
              className={`tab-btn ${activeTab === 'scoring' ? 'active' : ''}`}
              onClick={() => setActiveTab('scoring')}
            >
              Keypad
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === 'scorecard' ? 'active' : ''}`}
              onClick={() => setActiveTab('scorecard')}
            >
              Scorecard
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === 'teams' ? 'active' : ''}`}
              onClick={() => setActiveTab('teams')}
            >
              Teams & Players
            </button>
          </div>
        </div>
      </header>

      {/* Error alert */}
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button type="button" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Main Content Area */}
      {activeTab === 'teams' ? (
        <TeamsPlayersView />
      ) : loading ? (
        <div className="loading-state">Loading match data...</div>
      ) : !innings ? (
        <div className="empty-state">
          <h3>No Active Innings</h3>
          <p>This match has not started an innings yet.</p>
          <button
            type="button"
            className="btn btn-brand"
            style={{ marginTop: '12px' }}
            onClick={() => setIsNewMatchModalOpen(true)}
          >
            Start New Match
          </button>
        </div>
      ) : (
        <main className="main-content">
          {/* Main Score Banner */}
          <ScoreBanner
            match={match}
            innings={innings}
            scorecard={scorecard}
            matchSummary={matchSummary}
          />

          {activeTab === 'scoring' ? (
            <div className="scoring-screen">
              {/* Match Completed Card */}
              {match?.status === 'COMPLETED' ? (
                <div className="match-completed-card">
                  <h3>🎉 Match Completed!</h3>
                  <p className="winner-announcement">{matchSummary || 'Match Finished'}</p>
                  <button
                    type="button"
                    className="btn btn-brand"
                    onClick={() => setActiveTab('scorecard')}
                  >
                    View Match Scorecard
                  </button>
                </div>
              ) : innings.status === 'COMPLETED' && innings.innings_number === 1 ? (
                /* Innings Break Card */
                <div className="innings-break-card">
                  <h3>⏸️ Innings 1 Complete!</h3>
                  <p>
                    {innings.batting_team?.name} posted <strong>{scorecard?.total_runs}</strong> runs.
                    Target for {innings.bowling_team?.name}: <strong>{(scorecard?.total_runs || 0) + 1}</strong> runs.
                  </p>
                  <button
                    type="button"
                    className="btn btn-brand btn-large"
                    onClick={handleStartNextInnings}
                  >
                    ▶️ Start 2nd Innings
                  </button>
                </div>
              ) : (
                <>
                  {/* Batters & Bowler Active HUD */}
                  <BattersBowlerHUD
                    strikerId={strikerId}
                    nonStrikerId={nonStrikerId}
                    bowlerId={bowlerId}
                    onStrikerChange={setStrikerId}
                    onNonStrikerChange={setNonStrikerId}
                    onBowlerChange={setBowlerId}
                    battingSquad={battingSquad}
                    bowlingSquad={fieldingSquad}
                    scorecard={scorecard}
                    deliveries={deliveries}
                    maxOvers={innings?.max_overs}
                  />

                  {/* Over Ticker */}
                  <OverTicker deliveries={deliveries} />

                  {/* Over completion notice */}
                  {isOverComplete && (
                    <div className="over-complete-alert">
                      <span>🔔 Over completed! Change bowler for the next over.</span>
                    </div>
                  )}

                  {/* Fast Scoring Keypad */}
                  <ScoringKeypad
                    onScoreBall={handleScoreBall}
                    onOpenWicketModal={() => setIsWicketModalOpen(true)}
                    onUndoLastBall={handleUndo}
                    isOverComplete={isOverComplete}
                    disabled={innings.status === 'COMPLETED'}
                  />
                </>
              )}
            </div>
          ) : (
            /* Full Scorecard View */
            <ScorecardView scorecard={scorecard} matchScorecard={matchScorecard} />
          )}

          {/* Wicket Modal */}
          <WicketModal
            isOpen={isWicketModalOpen}
            onClose={() => setIsWicketModalOpen(false)}
            onConfirm={handleWicketConfirm}
            strikerId={strikerId}
            nonStrikerId={nonStrikerId}
            battingSquad={battingSquad}
            fieldingSquad={fieldingSquad}
          />
        </main>
      )}

      {/* New Match Modal */}
      <NewMatchModal
        isOpen={isNewMatchModalOpen}
        onClose={() => setIsNewMatchModalOpen(false)}
        onMatchCreated={handleNewMatchCreated}
      />
    </div>
  );
}
