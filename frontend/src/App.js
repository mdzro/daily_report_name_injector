
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import AnimatedLogo from './components/AnimatedLogo';

axios.defaults.withCredentials = true;

function App() {
  const [htmlFile, setHtmlFile] = useState(null);
  const [excelFile, setExcelFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await axios.get('/auth/status');
        setIsAuthenticated(Boolean(response.data?.authenticated));
      } catch (err) {
        setIsAuthenticated(false);
      }
    };

    checkAuth();
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const response = await axios.post('/auth/login', { password });
      if (response.data?.authenticated) {
        setIsAuthenticated(true);
        setPassword('');
      } else {
        setAuthError('Invalid password.');
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setAuthError('Invalid password.');
      } else {
        setAuthError('Unable to log in. Please try again.');
      }
      setIsAuthenticated(false);
    }
  };

  const handleLogout = async () => {
    try {
      await axios.post('/auth/logout');
    } catch (err) {
      // ignore logout errors
    }
    setIsAuthenticated(false);
    setHtmlFile(null);
    setExcelFile(null);
    setDownloadUrl('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setDownloadUrl('');
    if (!htmlFile || !excelFile) {
      setError('Please upload both files');
      return;
    }
    const formData = new FormData();
    formData.append('html_file', htmlFile);
    formData.append('excel_file', excelFile);
    try {
      setLoading(true);
      const response = await axios.post('/process', formData, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'text/html' });
      const url = window.URL.createObjectURL(blob);
      setDownloadUrl(url);
    } catch (err) {
      if (err.response?.status === 401) {
        setIsAuthenticated(false);
        setError('Your session has expired. Please log in again.');
      } else {
        setError('Failed to process files. Check server logs.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-8">
        <AnimatedLogo />
        <div className="bg-white p-8 rounded-2xl shadow-lg w-full max-w-md">
          <h1 className="text-2xl font-bold mb-6 text-center text-blue-700">Daily Report Name Injector</h1>
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div>
              <label className="block font-semibold mb-1" htmlFor="password">
                Enter Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full border border-gray-300 p-2 rounded-lg"
                required
              />
            </div>
            {authError && <p className="text-red-600 text-center">{authError}</p>}
            <button type="submit" className="bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700">
              Access Application
            </button>
          </form>
        </div>
        <p className="mt-8 text-sm text-gray-500">Enter the password to access the application.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-8">
      <AnimatedLogo />
      <div className="bg-white p-8 rounded-2xl shadow-lg w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center text-blue-700">Daily Report Name Injector</h1>
        <div className="flex justify-end mb-4">
          <button onClick={handleLogout} className="text-sm text-blue-600 hover:text-blue-800">
            Log out
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block font-semibold mb-1">HTML Daily Report</label>
            <input type="file" accept=".html" onChange={(e) => setHtmlFile(e.target.files[0])} className="block w-full border border-gray-300 p-2 rounded-lg" required />
          </div>
          <div>
            <label className="block font-semibold mb-1">Names Excel File</label>
            <input type="file" accept=".xlsx" onChange={(e) => setExcelFile(e.target.files[0])} className="block w-full border border-gray-300 p-2 rounded-lg" required />
          </div>
          {error && <p className="text-red-600 text-center">{error}</p>}
          <button type="submit" className="bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700" disabled={loading}>
            {loading ? 'Processing...' : 'Generate Updated Report'}
          </button>
        </form>
        {downloadUrl && (
          <a href={downloadUrl} download="report_with_names.html" className="block mt-6 text-center bg-green-600 text-white py-2 rounded-lg hover:bg-green-700">
            Download Updated Report
          </a>
        )}
      </div>
      <p className="mt-8 text-sm text-gray-500">Made with ❤️ for your daily reports</p>
    </div>
  );
}

export default App;
