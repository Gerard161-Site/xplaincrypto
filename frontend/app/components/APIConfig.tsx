'use client';

import { useState, useEffect } from 'react';

interface ApiStatus {
  enabled: boolean;
  has_key: boolean;
}

interface ApiConfig {
  [key: string]: ApiStatus;
}

export default function APIConfig() {
  const [apiConfig, setApiConfig] = useState<ApiConfig>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch API configuration
  useEffect(() => {
    fetchApiConfig();
  }, []);

  const fetchApiConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/config');
      
      if (!response.ok) {
        throw new Error('Failed to fetch API configuration');
      }
      
      const data = await response.json();
      setApiConfig(data.api_config || {});
      setError(null);
    } catch (err) {
      setError('Error fetching API configuration');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleApi = async (apiName: string) => {
    if (!apiConfig[apiName]) return;
    
    const newEnabled = !apiConfig[apiName].enabled;
    
    try {
      setLoading(true);
      const response = await fetch(`/api/config/${apiName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update API configuration');
      }
      
      // Update local state
      setApiConfig({
        ...apiConfig,
        [apiName]: {
          ...apiConfig[apiName],
          enabled: newEnabled,
        },
      });
      
      setSuccess(`${apiName} API ${newEnabled ? 'enabled' : 'disabled'} successfully`);
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Error updating API configuration');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (api: ApiStatus) => {
    if (!api.has_key) return 'text-yellow-500';
    return api.enabled ? 'text-green-500' : 'text-red-500';
  };

  const getStatusText = (api: ApiStatus) => {
    if (!api.has_key) return 'Missing API Key';
    return api.enabled ? 'Enabled' : 'Disabled';
  };

  return (
    <div className="bg-black/20 backdrop-blur-md rounded-lg p-4 shadow-lg">
      <h2 className="text-xl font-semibold mb-4">API Configuration</h2>
      
      {error && (
        <div className="bg-red-800/50 text-white p-2 rounded-md mb-4">
          {error}
        </div>
      )}
      
      {success && (
        <div className="bg-green-800/50 text-white p-2 rounded-md mb-4">
          {success}
        </div>
      )}
      
      {loading && !Object.keys(apiConfig).length ? (
        <div className="text-center py-4">Loading API configuration...</div>
      ) : (
        <div className="space-y-2">
          {Object.entries(apiConfig).map(([apiName, status]) => (
            <div key={apiName} className="flex items-center justify-between p-2 border-b border-gray-700">
              <div>
                <span className="capitalize">{apiName}</span>
                <span className={`ml-2 text-sm ${getStatusColor(status)}`}>
                  ({getStatusText(status)})
                </span>
              </div>
              
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={status.enabled}
                  onChange={() => toggleApi(apiName)}
                  disabled={loading || !status.has_key}
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
          ))}
        </div>
      )}
      
      <div className="mt-4 text-xs text-gray-400">
        <p>Note: API settings are reset when the server restarts.</p>
        <p>API keys are configured through environment variables.</p>
      </div>
    </div>
  );
} 