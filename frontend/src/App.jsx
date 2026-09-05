import React, { useState, useEffect } from 'react';
import { Sparkles, Upload, History, RefreshCw, Layers, CheckCircle, Clock, AlertCircle, Workflow, Trello, ExternalLink, Trash2 } from 'lucide-react';
import UploadScreen from './components/UploadScreen.jsx';
import TranscriptPane from './components/TranscriptPane.jsx';
import TaskPipelinePane from './components/TaskPipelinePane.jsx';

export default function App() {
  const [currentSession, setCurrentSession] = useState(null);
  const [sessionData, setSessionData] = useState(null);
  const [sessionsList, setSessionsList] = useState([]);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(false);

  // Fetch list of past sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  // Fetch current session details when session changes
  useEffect(() => {
    if (!currentSession?.id) return;
    loadSessionDetails(currentSession.id);
  }, [currentSession?.id]);

  // Auto-sync session data while processing (complements live WebSocket)
  useEffect(() => {
    if (!currentSession?.id) return;
    if (sessionData && sessionData.status !== 'processing') return;

    const interval = setInterval(() => {
      loadSessionDetails(currentSession.id);
    }, 3000);

    return () => clearInterval(interval);
  }, [currentSession?.id, sessionData?.status]);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/v1/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessionsList(data);
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
    }
  };

  const loadSessionDetails = async (id) => {
    setIsLoadingSession(true);
    try {
      const res = await fetch(`/api/v1/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSessionData(data);
      }
    } catch (e) {
      console.error('Failed to load session details:', e);
    } finally {
      setIsLoadingSession(false);
    }
  };

  const handleDeleteSession = async (id, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this session? This action cannot be undone.')) {
      return;
    }

    try {
      const res = await fetch(`/api/v1/sessions/${id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        // If current session was deleted, clear it
        if (currentSession?.id === id) {
          setCurrentSession(null);
          setSessionData(null);
        }
        await fetchSessions();
      } else {
        alert('Failed to delete session');
      }
    } catch (err) {
      console.error('Error deleting session:', err);
      alert('Error deleting session');
    }
  };

  const handleSessionCreated = (session) => {
    setCurrentSession(session);
    setSessionData({
      id: session.id,
      name: session.name,
      status: session.status,
      created_at: session.created_at,
      transcript_segments: [],
      items: [],
    });
    fetchSessions();
  };

  const handleSelectSession = (s) => {
    setCurrentSession(s);
    setSessionData(null);
    setShowHistoryDrawer(false);
  };

  const handleNewUpload = () => {
    setCurrentSession(null);
    setSessionData(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Top Application Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={handleNewUpload}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 p-0.5 shadow-lg shadow-indigo-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center text-indigo-400">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>
            <div>
              <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-1.5 font-display">
                AgentFlow <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">v0.1</span>
              </span>
              <p className="text-[11px] text-slate-400 font-medium">Meeting-to-Action AI Pipeline</p>
            </div>
          </div>

          {/* Navigation Actions */}
          <div className="flex items-center space-x-2">
            {/* Quick Link: n8n Workflow */}
            <a
              href={import.meta.env.VITE_N8N_URL || 'http://localhost:5678'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-850 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700/60 transition-all shadow-sm"
              title="Open n8n Automation Canvas"
            >
              <Workflow className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline">n8n Workflow</span>
              <ExternalLink className="w-3 h-3 text-slate-500" />
            </a>

            {/* Quick Link: Trello Board */}
            <a
              href={import.meta.env.VITE_TRELLO_BOARD_URL || 'https://trello.com'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-850 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700/60 transition-all shadow-sm"
              title="Open Trello Task Board"
            >
              <Trello className="w-3.5 h-3.5 text-blue-400" />
              <span className="hidden sm:inline">Trello Board</span>
              <ExternalLink className="w-3 h-3 text-slate-500" />
            </a>

            <div className="h-4 w-px bg-slate-800 mx-1 hidden sm:block" />

            {currentSession && (
              <button
                onClick={handleNewUpload}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700/60 transition-all"
              >
                <Upload className="w-3.5 h-3.5 text-indigo-400" />
                <span className="hidden sm:inline">New Upload</span>
              </button>
            )}

            <button
              onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700/60 transition-all"
            >
              <History className="w-3.5 h-3.5 text-purple-400" />
              <span>Sessions ({sessionsList.length})</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 flex flex-col space-y-6">
        {!currentSession ? (
          /* View 1: Upload Screen */
          <UploadScreen onSessionCreated={handleSessionCreated} />
        ) : (
          /* View 2: Live Session View */
          <div className="flex flex-col space-y-6 flex-1">
            {/* Session Header Card */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <Layers className="w-3 h-3" />
                    Session ID: {currentSession.id.slice(0, 8)}...
                  </span>
                  <span className="text-xs text-slate-500">
                    Created: {new Date(currentSession.created_at || Date.now()).toLocaleTimeString()}
                  </span>
                </div>
                <h1 className="text-xl font-bold text-slate-100">
                  {currentSession.name || 'Meeting Recording Session'}
                </h1>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 self-start md:self-auto">
                <button
                  onClick={() => loadSessionDetails(currentSession.id)}
                  disabled={isLoadingSession}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700/60 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSession ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>

                <button
                  onClick={(e) => handleDeleteSession(currentSession.id, e)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-950/40 hover:bg-red-900/60 text-red-300 text-xs font-medium border border-red-800/40 transition-colors"
                  title="Delete this session"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  <span>Delete</span>
                </button>
              </div>
            </div>

            {/* Split View: Transcript Pane (Left) + Task Pipeline Pane (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-[500px]">
              <TranscriptPane
                sessionId={currentSession.id}
                initialSegments={sessionData?.transcript_segments || []}
                isProcessing={sessionData?.status === 'processing'}
              />
              <TaskPipelinePane
                sessionId={currentSession.id}
                initialItems={sessionData?.items || []}
                isProcessing={sessionData?.status === 'processing'}
              />
            </div>
          </div>
        )}
      </main>

      {/* History Drawer Modal */}
      {showHistoryDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-md bg-slate-900 border-l border-slate-800 p-6 flex flex-col h-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <History className="w-4 h-4 text-indigo-400" />
                Session History
              </h2>
              <button
                onClick={() => setShowHistoryDrawer(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {sessionsList.length === 0 ? (
                <p className="text-slate-400 text-xs text-center py-8">No sessions recorded yet.</p>
              ) : (
                sessionsList.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => handleSelectSession(s)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer group ${
                      currentSession?.id === s.id
                        ? 'bg-indigo-600/15 border-indigo-500/40 text-white'
                        : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold truncate text-slate-100 flex-1 pr-2">{s.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-slate-400">
                          {new Date(s.created_at).toLocaleDateString()}
                        </span>
                        <button
                          onClick={(e) => handleDeleteSession(s.id, e)}
                          className="p-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-950/30 transition-colors opacity-70 group-hover:opacity-100"
                          title="Delete session"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>{s.item_count} action items</span>
                      <span className="capitalize text-indigo-400">{s.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
