
import React, { useMemo, useState } from 'react';
import axios from 'axios';

const CREDENTIALS = {
  admin: { username: 'admin', password: 'admin123' },
  user: { username: 'user', password: 'user123' },
};

function App() {
  const [htmlFile, setHtmlFile] = useState(null);
  const [excelFile, setExcelFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [role, setRole] = useState('');

  const credentialHints = useMemo(
    () =>
      Object.entries(CREDENTIALS)
        .map(([roleKey, creds]) => `${roleKey}: ${creds.username} / ${creds.password}`)
        .join(' | '),
    []
  );

  const handleLogin = (e) => {
    e.preventDefault();
    setAuthError('');
    const matchedRole = Object.entries(CREDENTIALS).find(
      ([roleKey, creds]) => creds.username === username.trim() && creds.password === password
    );

    if (!matchedRole) {
      setAuthError('Invalid username or password. Please try again.');
      return;
    }

    setRole(matchedRole[0]);
    setUsername('');
    setPassword('');
  };

  const handleLogout = () => {
    setRole('');
    setHtmlFile(null);
    setExcelFile(null);
    setDownloadUrl('');
    setError('');
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
      const response = await axios.post('/process', formData, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'text/html' });
      const url = window.URL.createObjectURL(blob);
      setDownloadUrl(url);
    } catch (err) {
      setError('Failed to process files. Check server logs.');
    } finally {
      setLoading(false);
    }
  };

  if (!role) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex flex-col items-center justify-center p-6">
        <div className="bg-white shadow-xl rounded-2xl p-8 w-full max-w-md border border-slate-100">
          <h1 className="text-3xl font-bold text-center text-blue-700 mb-2">Welcome Back</h1>
          <p className="text-center text-gray-500 mb-6">Sign in to access the Daily Report tools.</p>
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div>
              <label className="block font-semibold text-sm text-gray-700 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                placeholder="Enter your username"
                required
              />
            </div>
            <div>
              <label className="block font-semibold text-sm text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                placeholder="Enter your password"
                required
              />
            </div>
            {authError && <p className="text-red-600 text-center text-sm">{authError}</p>}
            <button
              type="submit"
              className="bg-blue-600 text-white py-2 rounded-lg font-semibold hover:bg-blue-700 transition"
            >
              Sign In
            </button>
          </form>
          <p className="mt-6 text-xs text-gray-400 text-center">
            Default credentials &mdash; {credentialHints}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col gap-6 items-center py-10 px-6">
      <header className="w-full max-w-5xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-blue-700">Daily Report Name Injector</h1>
          <p className="text-sm text-gray-500">Logged in as <span className="font-semibold capitalize">{role}</span></p>
        </div>
        <button
          onClick={handleLogout}
          className="self-start sm:self-auto bg-white border border-gray-300 px-4 py-2 rounded-lg shadow-sm hover:bg-gray-50"
        >
          Log out
        </button>
      </header>

      {role === 'admin' && (
        <section className="w-full max-w-5xl bg-white rounded-2xl shadow-md p-6 border border-blue-100">
          <h2 className="text-xl font-semibold text-blue-600 mb-3">Admin Dashboard</h2>
          <p className="text-gray-600 mb-4">
            Monitor the status of incoming report batches, share credentials with teammates, and ensure the
            latest templates are ready for processing.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
              <p className="text-sm text-gray-500">Today&apos;s processed reports</p>
              <p className="text-3xl font-bold text-blue-700">12</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
              <p className="text-sm text-gray-500">Pending approvals</p>
              <p className="text-3xl font-bold text-blue-700">3</p>
            </div>
          </div>
        </section>
      )}

      <section className="w-full max-w-3xl bg-white p-8 rounded-2xl shadow-lg">
        <h2 className="text-2xl font-semibold mb-6 text-center text-blue-700">Generate Updated Daily Report</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block font-semibold mb-1">HTML Daily Report</label>
            <input
              type="file"
              accept=".html"
              onChange={(e) => setHtmlFile(e.target.files[0])}
              className="block w-full border border-gray-300 p-2 rounded-lg"
              required
            />
          </div>
          <div>
            <label className="block font-semibold mb-1">Names Excel File</label>
            <input
              type="file"
              accept=".xlsx"
              onChange={(e) => setExcelFile(e.target.files[0])}
              className="block w-full border border-gray-300 p-2 rounded-lg"
              required
            />
          </div>
          {error && <p className="text-red-600 text-center">{error}</p>}
          <button type="submit" className="bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700" disabled={loading}>
            {loading ? 'Processing...' : 'Generate Updated Report'}
          </button>
        </form>
        {downloadUrl && (
          <a
            href={downloadUrl}
            download="report_with_names.html"
            className="block mt-6 text-center bg-green-600 text-white py-2 rounded-lg hover:bg-green-700"
          >
            Download Updated Report
          </a>
        )}
      </section>
      <p className="text-sm text-gray-500">Made with ❤️ for your daily reports</p>
    </div>
  );
}

export default App;
