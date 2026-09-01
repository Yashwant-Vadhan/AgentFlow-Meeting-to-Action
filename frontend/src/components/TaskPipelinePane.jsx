import React, { useState, useEffect, useRef } from 'react';
import {
  ListCheck,
  CheckCircle2,
  XCircle,
  Clock,
  User,
  Calendar,
  Quote,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  ExternalLink,
  Sparkles,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';

export default function TaskPipelinePane({ sessionId, initialItems = [] }) {
  const [items, setItems] = useState(initialItems);
  const [expandedId, setExpandedId] = useState(null);
  const [filterType, setFilterType] = useState('all'); // all | action_item | decision
  const [updatingId, setUpdatingId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const wsRef = useRef(null);

  // Sync initial items
  useEffect(() => {
    if (initialItems && initialItems.length > 0) {
      setItems((prev) => {
        const itemMap = new Map();
        prev.forEach((it) => itemMap.set(it.id, it));
        initialItems.forEach((it) => itemMap.set(it.id, it));
        return Array.from(itemMap.values());
      });
    }
  }, [initialItems]);

  // Connect to WebSocket for live task updates
  useEffect(() => {
    if (!sessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsHost = window.location.port === '5173' ? 'localhost:8000' : host;
    const wsUrl = `${protocol}//${wsHost}/ws/sessions/${sessionId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'task_update' && message.data) {
          const updatedItem = message.data;
          setItems((prev) => {
            const index = prev.findIndex((it) => it.id === updatedItem.id);
            if (index !== -1) {
              const copy = [...prev];
              copy[index] = { ...copy[index], ...updatedItem };
              return copy;
            } else {
              return [updatedItem, ...prev];
            }
          });
        }
      } catch (e) {
        console.error('[WebSocket] Error parsing task update:', e);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [sessionId]);

  // Approve / Reject Handler
  const handleStatusUpdate = async (itemId, newStatus) => {
    if (updatingId) return;

    setUpdatingId(itemId);
    setActionError(null);

    // Backup current item state for rollback
    const originalItems = [...items];

    // Optimistic Update
    setItems((prev) =>
      prev.map((it) =>
        it.id === itemId
          ? {
              ...it,
              status: newStatus === 'approved' ? 'routed' : 'rejected',
              pipeline_status: newStatus === 'approved' ? 'routed' : 'rejected',
              verification_status: newStatus,
            }
          : it
      )
    );

    try {
      const response = await fetch(`/api/v1/sessions/${sessionId}/items/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update status (${response.status})`);
      }

      const resData = await response.json();
      setItems((prev) =>
        prev.map((it) => (it.id === itemId ? { ...it, ...resData } : it))
      );
    } catch (err) {
      console.error('Failed to update task status:', err);
      setActionError(`Failed to update task: ${err.message}`);
      // Rollback
      setItems(originalItems);
    } finally {
      setUpdatingId(null);
    }
  };

  const toggleExpand = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const getItemBadge = (item) => {
    const status = (item.status || item.pipeline_status || 'extracted').toLowerCase();

    switch (status) {
      case 'routed':
      case 'approved':
        return {
          label: 'Routed',
          ariaLabel: 'Status: Routed to workflow',
          className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          icon: <CheckCircle2 className="w-3 h-3" />,
        };
      case 'verified':
        return {
          label: 'Verified',
          ariaLabel: 'Status: Verified by AI',
          className: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
          icon: <CheckCircle2 className="w-3 h-3" />,
        };
      case 'needs_review':
        return {
          label: 'Needs Review',
          ariaLabel: 'Status: Needs manual review',
          className: 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse',
          icon: <Clock className="w-3 h-3" />,
        };
      case 'rejected':
        return {
          label: 'Rejected',
          ariaLabel: 'Status: Rejected',
          className: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
          icon: <XCircle className="w-3 h-3" />,
        };
      case 'failed':
        return {
          label: 'Failed',
          ariaLabel: 'Status: Failed routing',
          className: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
          icon: <AlertCircle className="w-3 h-3" />,
        };
      case 'extracted':
      default:
        return {
          label: 'Extracted',
          ariaLabel: 'Status: Extracted candidate',
          className: 'bg-slate-800 text-slate-300 border-slate-700',
          icon: <Sparkles className="w-3 h-3" />,
        };
    }
  };

  const filteredItems = items.filter((it) => {
    if (filterType === 'all') return true;
    return it.type === filterType;
  });

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      {/* Pane Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/60 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <ListCheck className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              Extracted Action Items & Decisions
              <span className="text-[10px] font-normal text-slate-400">({items.length} items)</span>
            </h2>
            <p className="text-[11px] text-slate-400">AI Extractor & Verifier Agent Pipeline</p>
          </div>
        </div>

        {/* Filter Toggle */}
        <div className="flex items-center space-x-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700/60 text-[11px]">
          <button
            onClick={() => setFilterType('all')}
            className={`px-2 py-0.5 rounded font-medium transition-all ${
              filterType === 'all' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilterType('action_item')}
            className={`px-2 py-0.5 rounded font-medium transition-all ${
              filterType === 'action_item' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Actions
          </button>
          <button
            onClick={() => setFilterType('decision')}
            className={`px-2 py-0.5 rounded font-medium transition-all ${
              filterType === 'decision' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Decisions
          </button>
        </div>
      </div>

      {/* Action Error Banner */}
      {actionError && (
        <div className="p-3 bg-rose-500/10 border-b border-rose-500/20 text-rose-300 text-xs flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-rose-400 hover:underline text-[10px]">
            Dismiss
          </button>
        </div>
      )}

      {/* Item List Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3.5 min-h-[300px]">
        {filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[260px] text-center p-6 space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-800/60 border border-slate-700/50 flex items-center justify-center text-slate-400 animate-subtle-pulse">
              <ListCheck className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">No action items extracted yet</p>
              <p className="text-xs text-slate-400 mt-1 max-w-xs">
                Candidate tasks will appear here as soon as the Extractor Agent processes the transcript.
              </p>
            </div>
          </div>
        ) : (
          filteredItems.map((item) => {
            const badge = getItemBadge(item);
            const isExpanded = expandedId === item.id;
            const statusStr = (item.status || item.pipeline_status || '').toLowerCase();
            const needsReview = statusStr === 'needs_review';

            return (
              <div
                key={item.id}
                className={`glass-card glass-card-hover rounded-xl border transition-all duration-200 overflow-hidden ${
                  needsReview ? 'border-amber-500/30 bg-amber-500/[0.03]' : 'border-slate-800'
                }`}
              >
                {/* Main Card Header */}
                <div className="p-4 cursor-pointer" onClick={() => toggleExpand(item.id)}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    {/* Badge + Type */}
                    <div className="flex items-center space-x-2 shrink-0">
                      <span
                        aria-label={badge.ariaLabel}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badge.className}`}
                      >
                        {badge.icon}
                        <span>{badge.label}</span>
                      </span>

                      <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded border border-slate-700/50">
                        {item.type === 'decision' ? 'Decision' : 'Action Item'}
                      </span>
                    </div>

                    {/* Expand Toggle */}
                    <button
                      type="button"
                      aria-label="Toggle details"
                      className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800/60 transition-colors"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Task Description */}
                  <h3 className="text-sm font-semibold text-slate-100 leading-snug mb-3">
                    {item.description}
                  </h3>

                  {/* Meta Footer (Owner & Deadline) */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 pt-2 border-t border-slate-800/60">
                    <div className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Owner: <strong className="text-slate-200 font-medium">{item.owner || 'Unassigned'}</strong></span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-purple-400" />
                      <span>Deadline: <strong className="text-slate-200 font-medium">{item.deadline || 'None'}</strong></span>
                    </div>

                    {item.confidence != null && (
                      <div className="ml-auto text-[11px] font-mono text-slate-400">
                        Confidence: <span className="text-slate-200">{(item.confidence * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Approve / Reject Controls for needs_review cards */}
                {needsReview && (
                  <div className="px-4 py-3 bg-amber-500/10 border-t border-amber-500/20 flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-amber-300 flex items-center gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                      Action required: Verify item validity
                    </span>
                    <div className="flex items-center space-x-2 shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusUpdate(item.id, 'rejected');
                        }}
                        disabled={updatingId === item.id}
                        className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-semibold border border-rose-500/30 transition-all active:scale-95 disabled:opacity-50"
                      >
                        Reject
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusUpdate(item.id, 'approved');
                        }}
                        disabled={updatingId === item.id}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all active:scale-95 disabled:opacity-50 flex items-center gap-1"
                      >
                        {updatingId === item.id && <RefreshCw className="w-3 h-3 animate-spin" />}
                        <span>Approve & Route</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Expandable Quote Details */}
                {isExpanded && (
                  <div className="px-4 py-3.5 bg-slate-900/80 border-t border-slate-800 text-xs space-y-2 animate-fadeIn">
                    {item.source_quote && (
                      <div className="space-y-1">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                          <Quote className="w-3 h-3 text-indigo-400" />
                          Source Quote Grounding
                        </span>
                        <blockquote className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-slate-300 italic">
                          "{item.source_quote}"
                        </blockquote>
                      </div>
                    )}

                    {item.verification_reason && (
                      <div className="space-y-0.5 pt-1">
                        <span className="text-[11px] font-semibold text-slate-400">Verification Note:</span>
                        <p className="text-slate-300">{item.verification_reason}</p>
                      </div>
                    )}

                    {item.trello_card_url && (
                      <div className="pt-1">
                        <a
                          href={item.trello_card_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-indigo-400 hover:underline font-medium text-xs"
                        >
                          <span>View Trello Card</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
