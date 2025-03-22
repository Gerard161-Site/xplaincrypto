'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';

interface SocketContextProps {
  socket: Socket | null;
  connected: boolean;
  progress: string[];
  reportUrl: string | null;
  isGenerating: boolean;
  startGenerate: (projectName: string, fastMode: boolean) => void;
  resetState: () => void;
  metrics: any;
  logs: string[];
}

const SocketContext = createContext<SocketContextProps>({
  socket: null,
  connected: false,
  progress: [],
  reportUrl: null,
  isGenerating: false,
  startGenerate: () => {},
  resetState: () => {},
  metrics: null,
  logs: [],
});

export const useSocket = () => useContext(SocketContext);

interface SocketProviderProps {
  children: ReactNode;
}

export const SocketProvider: React.FC<SocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    // Initialize socket connection
    const socketInstance = io('http://localhost:8000', {
      // Use default transports, don't limit to websocket only
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      timeout: 60000, // 60 second timeout
    });

    socketInstance.on('connect', () => {
      console.log('Connected to server');
      setConnected(true);
      setLogs(prev => [...prev, "INFO - Connected to backend server"]);
    });

    socketInstance.on('disconnect', () => {
      console.log('Disconnected from server');
      setConnected(false);
      setLogs(prev => [...prev, "WARNING - Disconnected from backend server"]);
    });

    socketInstance.on('connect_error', (error) => {
      console.error('Connection error:', error);
      setLogs(prev => [...prev, `ERROR - Connection error: ${error.message}`]);
    });

    socketInstance.on('progress', (data) => {
      console.log('Progress update:', data);
      setProgress((prev) => [...prev, data.message]);
    });

    socketInstance.on('error', (data) => {
      console.error('Error from server:', data);
      setProgress((prev) => [...prev, `Error: ${data}`]);
      setLogs(prev => [...prev, `ERROR - ${data}`]);
      setIsGenerating(false);
    });

    socketInstance.on('data', (data) => {
      console.log('Report data received:', data);
      if (data.pdf_path) {
        setReportUrl(data.pdf_path);
      }
      if (data.metrics) {
        setMetrics(data.metrics);
      }
      setProgress((prev) => [...prev, data.status || 'Report generation completed']);
      setIsGenerating(false);
    });

    socketInstance.on('log_update', (data) => {
      console.log('Log update:', data.message);
      setLogs((prev) => [...prev, data.message]);
    });

    setSocket(socketInstance);

    return () => {
      socketInstance.disconnect();
    };
  }, []);

  const startGenerate = (projectName: string, fastMode: boolean = false) => {
    if (socket && connected) {
      console.log(`Starting generation for ${projectName} with fastMode=${fastMode}`);
      setProgress([`Starting generation for ${projectName}...`]);
      setReportUrl(null);
      setMetrics(null);
      setLogs([`INFO - Starting report generation for ${projectName}`]);
      setIsGenerating(true);
      socket.emit('message', { project_name: projectName, fast_mode: fastMode });
    } else {
      console.error('Socket not connected');
      setLogs(prev => [...prev, "ERROR - Socket not connected, cannot generate report"]);
      alert("Cannot connect to the server. Please check if the backend is running.");
    }
  };

  const resetState = () => {
    setProgress([]);
    setReportUrl(null);
    setIsGenerating(false);
    setMetrics(null);
    setLogs([]);
  };

  return (
    <SocketContext.Provider value={{ 
      socket, 
      connected, 
      progress, 
      reportUrl, 
      isGenerating, 
      startGenerate, 
      resetState, 
      metrics,
      logs
    }}>
      {children}
    </SocketContext.Provider>
  );
}; 