import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, AlertTriangle, Copy, Check, ArrowDown, Wifi, WifiOff } from 'lucide-react';

export default function TranscriptPane({ sessionId, initialSegments = [], isProcessing = false }) {
  const [segments, setSegments] = useState(initialSegments);
  const [isConnected, setIsConnected] = useState(false);
  const [copied, setCopied] = useState(false);
  const [userScrolled, setUserScrolled] = useState(false);
  const scrollContainerRef = useRef(null);
  const wsRef = useRef(null);

  // Sync initial segments if provided
  useEffect(() => {
    if (initialSegments && initialSegments.length > 0) {
      setSegments((prev) => {
        // Merge without duplicates based on start time + text
        const map = new Map();
        prev.forEach((s) => map.set(`${s.start}-${s.text}`, s));
        initialSegments.forEach((s) => map.set(`${s.start}-${s.text}`, s));
        return Array.from(map.values()).sort((a, b) => a.start - b.start);
      });
    }
  }, [initialSegments]);

  // Connect to WebSocket
  useEffect(() => {
    if (!sessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    // If running under Vite dev server (port 5173), direct WS to 8000 if not proxied
    const wsHost = window.location.port === '5173' ? 'localhost:8000' : host;
    const wsUrl = `${protocol}//${wsHost}/ws/sessions/${sessionId}`;

    console.log('[WebSocket] Connecting to:', wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'transcript_segment' && message.data) {
          const newSeg = message.data;
          setSegments((prev) => {
            // Avoid adding identical duplicate segments
            if (prev.some((s) => s.start === newSeg.start && s.text === newSeg.text)) {
              return prev;
            }
            return [...prev, newSeg].sort((a, b) => a.start - b.start);
          });
        }
      } catch (e) {
        console.error('[WebSocket] Error parsing message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected');
      setIsConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [sessionId]);

  // Auto-scroll logic
  useEffect(() => {
    if (!userScrolled && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [segments, userScrolled]);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    // User is considered scrolled up if they are >50px from bottom
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setUserScrolled(!isAtBottom);
  };

  const scrollToBottom = () => {
    setUserScrolled(false);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  };

  const formatTimestamp = (seconds) => {
    if (seconds == null) return '[00:00]';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `[${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}]`;
  };

  const copyTranscriptText = () => {
    const text = segments.map((s) => `${formatTimestamp(s.start)} ${s.text}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      {/* Pane Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/60 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              Live Transcript Feed
              <span className="text-[10px] font-normal text-slate-400">({segments.length} lines)</span>
            </h2>
            <p className="text-[11px] text-slate-400">Realtime Whisper speech-to-text output</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Live WS Status Indicator */}
          <div
            title={isConnected ? 'WebSocket connected' : 'WebSocket connecting / disconnected'}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
              isConnected
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-amber-500/10 border-amber-500/20 text-amber-400 animate-pulse'
            }`}
          >
            {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span>{isConnected ? 'Live' : 'Connecting'}</span>
          </div>

          {/* Copy Button */}
          {segments.length > 0 && (
            <button
              onClick={copyTranscriptText}
              title="Copy transcript to clipboard"
              className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/60"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Scrolling Content Area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3 relative min-h-[300px]"
      >
        {segments.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[260px] text-center p-6 space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-800/60 border border-slate-700/50 flex items-center justify-center text-slate-400 animate-subtle-pulse">
              <MessageSquare className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">Waiting for transcript...</p>
              <p className="text-xs text-slate-400 mt-1 max-w-xs">
                {isProcessing
                  ? 'Whisper model is processing audio chunks. Lines will appear live.'
                  : 'Upload an audio recording to start streaming transcript segments.'}
              </p>
            </div>
          </div>
        ) : (
          segments.map((seg, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-xl border transition-all duration-200 text-sm leading-relaxed ${
                seg.low_confidence
                  ? 'bg-amber-500/5 border-amber-500/20 text-slate-200'
                  : 'bg-slate-900/40 border-slate-800/80 text-slate-100 hover:border-slate-700/80'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-mono font-semibold text-indigo-400/90 tracking-wider">
                  {formatTimestamp(seg.start)}
                </span>
                {seg.low_confidence && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                    <AlertTriangle className="w-3 h-3" />
                    Low confidence
                  </span>
                )}
              </div>
              <p className="text-slate-200 text-sm font-normal">{seg.text}</p>
            </div>
          ))
        )}

        {/* Floating Scroll to Bottom Button */}
        {userScrolled && segments.length > 0 && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-4 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all animate-bounce"
          >
            <span>Scroll to bottom</span>
            <ArrowDown className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
