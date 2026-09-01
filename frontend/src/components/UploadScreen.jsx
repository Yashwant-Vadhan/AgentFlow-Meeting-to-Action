import React, { useState, useRef } from 'react';
import { UploadCloud, FileAudio, AlertCircle, Sparkles, CheckCircle2, ArrowRight } from 'lucide-react';

export default function UploadScreen({ onSessionCreated }) {
  const [file, setFile] = useState(null);
  const [sessionName, setSessionName] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef(null);

  const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.mp4', '.mov', '.mkv', '.webm'];
  const MAX_SIZE_MB = 200;
  const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

  const validateFile = (selectedFile) => {
    if (!selectedFile) return false;

    const ext = '.' + selectedFile.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Invalid file format (${ext}). Allowed: Audio (.mp3, .wav, .m4a) & Video (.mp4, .mov, .mkv, .webm)`);
      return false;
    }

    if (selectedFile.size > MAX_SIZE_BYTES) {
      const sizeMb = (selectedFile.size / (1024 * 1024)).toFixed(1);
      setError(`File size (${sizeMb}MB) exceeds maximum allowed limit of ${MAX_SIZE_MB}MB.`);
      return false;
    }

    setError(null);
    return true;
  };

  const handleFileSelect = (selectedFile) => {
    if (validateFile(selectedFile)) {
      setFile(selectedFile);
    } else {
      setFile(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    if (sessionName.trim()) {
      formData.append('name', sessionName.trim());
    }

    try {
      const response = await fetch('/api/v1/sessions', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
      }

      const session = await response.json();
      if (onSessionCreated) {
        onSessionCreated(session);
      }
    } catch (err) {
      console.error('Failed to create session:', err);
      setError(err.message || 'Failed to connect to backend server. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-120px)] p-4 sm:p-6">
      {/* Title Header */}
      <div className="text-center max-w-xl mb-8 space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold tracking-wide uppercase">
          <Sparkles className="w-3.5 h-3.5" />
          Autonomous Meeting Intelligence
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Transform Meetings into <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">Action Items</span>
        </h1>
        <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
          Upload your meeting recording to transcribe audio locally, extract grounded commitments, and automatically route verified tasks.
        </p>
      </div>

      {/* Main Glassmorphic Card */}
      <div className="w-full max-w-[480px] glass-panel rounded-2xl p-6 sm:p-8 shadow-2xl border border-slate-800 relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />

        <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
          {/* Dropzone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative group border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 ${
              isDragging
                ? 'border-indigo-500 bg-indigo-500/10 scale-[1.01]'
                : file
                ? 'border-emerald-500/40 bg-emerald-500/5'
                : 'border-slate-700 hover:border-indigo-500/50 hover:bg-slate-800/40 bg-slate-900/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a"
              onChange={(e) => e.target.files && handleFileSelect(e.target.files[0])}
              className="hidden"
            />

            {!file ? (
              <div className="flex flex-col items-center space-y-3">
                <div className="w-14 h-14 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-200">
                    <span className="text-indigo-400 hover:underline">Click to browse</span> or drop audio file
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Supports MP3, WAV, M4A (Max 200MB)
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between p-2">
                <div className="flex items-center space-x-3 text-left overflow-hidden">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                    <FileAudio className="w-5 h-5" />
                  </div>
                  <div className="truncate">
                    <p className="text-xs font-semibold text-slate-200 truncate">{file.name}</p>
                    <p className="text-[11px] text-slate-400">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-2 shrink-0">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      setError(null);
                    }}
                    className="text-xs text-slate-400 hover:text-rose-400 transition-colors ml-1 underline"
                  >
                    Change
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Inline Error Message */}
          {error && (
            <div className="flex items-start space-x-2.5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs animate-shake">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Session Name Input */}
          <div className="space-y-1.5">
            <label htmlFor="session-name" className="block text-xs font-medium text-slate-300">
              Session Title <span className="text-slate-500 font-normal">(optional)</span>
            </label>
            <input
              id="session-name"
              type="text"
              placeholder="e.g. Weekly Product Sync"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg bg-slate-900/70 border border-slate-700/80 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!file || isSubmitting}
            className={`w-full py-3 px-4 rounded-xl font-medium text-sm flex items-center justify-center space-x-2 shadow-lg transition-all duration-200 ${
              !file || isSubmitting
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
                : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-indigo-500/25 hover:shadow-indigo-500/40 active:scale-[0.99]'
            }`}
          >
            {isSubmitting ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Creating Session & Processing...</span>
              </>
            ) : (
              <>
                <span>Start Processing</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
