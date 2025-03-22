'use client';

import React, { useState, useEffect } from 'react';
import { useSocket } from './socket-provider';
import Spinner from './components/Spinner';

export default function Home() {
  const [projectName, setProjectName] = useState("");
  const [fastMode, setFastMode] = useState(true);
  const { connected, isGenerating, startGenerate, progress, reportUrl, resetState, metrics, logs } = useSocket();

  const handleGenerate = () => {
    if (!projectName) {
      alert("Please enter a project name");
      return;
    }
    if (!connected) {
      alert("Not connected to the server. Please wait for connection to establish or refresh the page.");
      return;
    }
    startGenerate(projectName, fastMode);
  };

  // Format duration in a user-friendly way
  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-blue-400">XplainCrypto</h1>
          <div className={`flex items-center ${connected ? 'text-green-500' : 'text-red-500'}`}>
            <div className={`w-3 h-3 rounded-full mr-2 ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            {connected ? 'Connected' : 'Disconnected'}
          </div>
        </div>
        
        <p className="text-gray-300 mb-8 text-center">
          Generate comprehensive, research-backed reports on any cryptocurrency
        </p>

        <div className="bg-gray-800 p-6 rounded-lg shadow-lg mb-6">
          <div className="mb-4">
            <label htmlFor="project-name" className="block text-gray-300 mb-2">
              Enter Cryptocurrency Name or Symbol:
            </label>
            <input
              id="project-name"
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="e.g., Bitcoin, Ethereum, SOL, etc."
              className="w-full p-2 bg-gray-700 text-white rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isGenerating}
            />
          </div>

          <div className="mb-6">
            <label className="block text-gray-300 mb-2">Report Mode:</label>
            <div className="flex space-x-4">
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={fastMode}
                  onChange={() => setFastMode(true)}
                  className="mr-2"
                  disabled={isGenerating}
                />
                <span className="text-gray-300">Fast Mode</span>
                <span className="ml-2 text-xs text-gray-500">(~1-2 min)</span>
              </label>
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={!fastMode}
                  onChange={() => setFastMode(false)}
                  className="mr-2"
                  disabled={isGenerating}
                />
                <span className="text-gray-300">Comprehensive Mode</span>
                <span className="ml-2 text-xs text-gray-500">(~5-10 min)</span>
              </label>
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={isGenerating || !connected}
            className={`w-full p-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 ${(isGenerating || !connected) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {connected ? 'Generate Report' : 'Connecting...'}
          </button>

          {isGenerating && (
            <div className="flex items-center gap-2 text-yellow-500 mt-4">
              <Spinner />
              Generating report... Please wait.
            </div>
          )}
          {reportUrl && (
            <div className="flex flex-col items-center gap-2 text-green-500 mt-4">
              <div className="flex items-center">
                <svg className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Report generated successfully!
              </div>
              <a 
                href={`http://localhost:8000${reportUrl}`} 
                target="_blank" 
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 text-white transition-colors mt-2"
              >
                Download PDF Report
              </a>
              {metrics && (
                <div className="text-xs text-gray-400 mt-2">
                  Generated in {formatDuration(metrics.duration)} | {metrics.mode === 'fast' ? 'Fast Mode' : 'Comprehensive Mode'}
                </div>
              )}
            </div>
          )}

          {/* Display log section */}
          <div className="mt-6 border border-gray-700 p-2 rounded">
            <h3 className="text-sm text-gray-400 mb-2">Process Log:</h3>
            <div className="bg-black rounded p-2 text-xs text-gray-300 font-mono h-64 overflow-y-auto">
              {logs.length > 0 ? (
                logs.map((log: string, idx: number) => (
                  <div 
                    key={idx} 
                    className={`mb-1 ${
                      log.includes('ERROR') 
                        ? 'text-red-400' 
                        : log.includes('WARNING') 
                          ? 'text-yellow-400' 
                          : 'text-green-400'
                    }`}
                  >
                    {log}
                  </div>
                ))
              ) : (
                <div className="text-gray-500">Logs will appear here during report generation...</div>
              )}
            </div>
          </div>

          <div className="mt-4 progress-log">
            <h3 className="text-sm text-gray-400 mb-2">Progress Updates:</h3>
            {progress.map((msg: string, idx: number) => (
              <p key={idx} className={`text-sm ${msg.includes('Error:') ? 'text-red-500' : 'text-gray-300'}`}>
                {msg}
              </p>
            ))}
          </div>
        </div>

        <div className="text-center text-gray-500 text-sm">
          <p>© 2023 XplainCrypto - AI-Powered Cryptocurrency Research</p>
        </div>
      </div>
    </main>
  );
}