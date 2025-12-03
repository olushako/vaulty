import { useState } from 'react';
import { setAuthToken } from '../lib/api';

const Auth = () => {
  const [token, setToken] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (token.trim()) {
      setAuthToken(token.trim());
      // Force page reload to update App component state
      window.location.reload();
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0d1117]">
      <div className="card p-8 w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="w-16 h-16 bg-primary-600 rounded-lg flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl font-bold text-white">V</span>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-[#c9d1d9]">Vaulty</h1>
          <p className="text-sm text-gray-500 dark:text-[#8b949e] mt-1">Secrets Manager</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-[#c9d1d9] mb-2">
              Authentication Token
            </label>
            <input
              type="text"
              required
              className="input"
              placeholder="Enter your master token or project token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <p className="text-xs text-gray-500 dark:text-[#8b949e] mt-1">
              Use a master token for full access or a project token for limited access.
            </p>
          </div>
          <button type="submit" className="btn btn-primary w-full">
            Authenticate
          </button>
        </form>
      </div>
    </div>
  );
};

export default Auth;

