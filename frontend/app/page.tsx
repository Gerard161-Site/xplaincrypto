'use client';

import React, { useState, useEffect } from 'react';
import { useSocket } from './socket-provider';
import Spinner from './components/Spinner';
import APIConfig from './components/APIConfig';

export default function Home() {
  const [projectName, setProjectName] = useState("");
  const [fastMode, setFastMode] = useState(true);
  const [activeTab, setActiveTab] = useState<'generate' | 'config'>('generate');
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

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <main className="min-h-screen text-white p-6 flex items-center justify-center">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-orange-400 to-pink-500">
            XplainCrypto
          </h1>
          <div className={`flex items-center ${connected ? 'text-green-400' : 'text-red-400'}`}>
            <div className={`w-4 h-4 rounded-full mr-2 ${connected ? 'bg-green-400' : 'bg-red-400'}`}></div>
            {connected ? 'Connected' : 'Disconnected'}
          </div>
        </div>

        {/* Tagline */}
        <p className="text-gray-200 text-lg mb-6 text-center">
          Generate comprehensive, research-backed reports on any cryptocurrency
        </p>

        {/* Tabs */}
        <div className="flex border-b border-gray-700 mb-4">
          <button
            className={`py-2 px-4 text-lg ${activeTab === 'generate' ? 'text-orange-400 border-b-2 border-orange-400' : 'text-gray-400'}`}
            onClick={() => setActiveTab('generate')}
          >
            Generate Report
          </button>
          <button
            className={`py-2 px-4 text-lg ${activeTab === 'config' ? 'text-orange-400 border-b-2 border-orange-400' : 'text-gray-400'}`}
            onClick={() => setActiveTab('config')}
          >
            API Configuration
          </button>
        </div>

        {activeTab === 'generate' ? (
          /* Main Report Generation Card */
          <div className="glass-card p-8">
            <div className="mb-6">
              <label htmlFor="project-name" className="block text-gray-200 text-lg mb-2">
                Enter Cryptocurrency Name or Symbol:
              </label>
              <input
                id="project-name"
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g., Bitcoin, Ethereum, SOL, etc."
                className="w-full p-3 bg-transparent border border-gray-400 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-400 transition-all"
                disabled={isGenerating}
              />
            </div>

            <div className="mb-8">
              <label className="block text-gray-200 text-lg mb-2">Report Mode:</label>
              <div className="flex space-x-6">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={fastMode}
                    onChange={() => setFastMode(true)}
                    className="mr-2 accent-orange-400"
                    disabled={isGenerating}
                  />
                  <span className="text-gray-200">Fast Mode</span>
                  <span className="ml-2 text-sm text-gray-400">(~1-2 min)</span>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={!fastMode}
                    onChange={() => setFastMode(false)}
                    className="mr-2 accent-orange-400"
                    disabled={isGenerating}
                  />
                  <span className="text-gray-200">Comprehensive Mode</span>
                  <span className="ml-2 text-sm text-gray-400">(~5-10 min)</span>
                </label>
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={isGenerating || !connected}
              className={`w-full p-3 gradient-button text-white rounded-lg flex items-center justify-center gap-2 ${(isGenerating || !connected) ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <svg
                className="h-6 w-6"
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
              <div className="flex items-center gap-2 text-orange-400 mt-6">
                <Spinner />
                Generating report... Please wait.
              </div>
            )}
            {reportUrl && (
              <div className="flex flex-col items-center gap-2 text-green-400 mt-6">
                <div className="flex items-center">
                  <svg className="h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Report generated successfully!
                </div>
                <a 
                  href={`http://localhost:8000${reportUrl}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="px-6 py-2 gradient-button rounded-lg text-white transition-colors mt-2"
                >
                  Download PDF Report
                </a>
                {metrics && (
                  <div className="text-sm text-gray-400 mt-2">
                    Generated in {formatDuration(metrics.duration)} | {metrics.mode === 'fast' ? 'Fast Mode' : 'Comprehensive Mode'}
                  </div>
                )}
              </div>
            )}

            {/* Process Log */}
            <div className="mt-8 border border-gray-600 p-3 rounded-lg">
              <h3 className="text-sm text-gray-400 mb-2">Process Log:</h3>
              <div className="log-console rounded-lg p-3 text-xs text-gray-300 font-mono h-64 overflow-y-auto">
                {logs.length > 0 ? (
                  logs.map((log: string, idx: number) => (
                    <div 
                      key={idx} 
                      className={`mb-1 ${
                        log.includes('ERROR') 
                          ? 'text-red-400' 
                          : log.includes('WARNING') 
                            ? 'text-orange-400' 
                            : 'text-green-300' 
                      }`}
                    >
                      {log}
                    </div>
                  ))
                ) : (
                  <div className="text-gray-400">Logs will appear here during report generation...</div>
                )}
              </div>
            </div>

            {/* Progress Updates */}
            <div className="mt-6 progress-log">
              <h3 className="text-sm text-gray-400 mb-2">Progress Updates:</h3>
              {progress.map((msg: string, idx: number) => (
                <p key={idx} className={`text-sm ${msg.includes('Error:') ? 'text-red-400' : 'text-gray-200'}`}>
                  {msg}
                </p>
              ))}
            </div>
          </div>
        ) : (
          /* API Configuration Card */
          <div className="glass-card p-8">
            <h2 className="text-2xl font-bold mb-4">API Configuration</h2>
            <p className="text-gray-300 mb-6">
              Enable or disable external API calls to different data providers. 
              This can be useful for debugging or when rate limits are reached.
            </p>
            <APIConfig />
          </div>
        )}

        {/* Footer */}
        <div className="text-center text-gray-400 text-sm mt-10">
          <p>© 2023 XplainCrypto - AI-Powered Cryptocurrency Research</p>
        </div>
      </div>
    </main>
  );
}