import { useState } from 'react';
import { apiRequest } from './api';

function Auth({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (event) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const payload = mode === 'login'
        ? { username: form.username, password: form.password }
        : {
            username: form.username,
            email: form.email,
            password: form.password,
            first_name: form.first_name,
            last_name: form.last_name,
          };

      const endpoint = mode === 'login' ? '/login/' : '/register/';
      const result = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      localStorage.setItem('saad_token', result.access);
      localStorage.setItem('saad_user', JSON.stringify(result.user));
      onAuth(result.user);
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <p className="eyebrow">SAAD</p>
          <h2>{mode === 'login' ? 'Clinic Login' : 'Create patient account'}</h2>
        </div>

        <div className="auth-toggle">
          <button
            className={mode === 'login' ? 'toggle active' : 'toggle'}
            onClick={() => setMode('login')}
          >
            Login
          </button>
          <button
            className={mode === 'signup' ? 'toggle active' : 'toggle'}
            onClick={() => setMode('signup')}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'signup' && (
            <>
              <input name="first_name" placeholder="First name" value={form.first_name} onChange={handleChange} />
              <input name="last_name" placeholder="Last name" value={form.last_name} onChange={handleChange} />
              <input name="email" type="email" placeholder="Email" value={form.email} onChange={handleChange} />
            </>
          )}

          <input name="username" placeholder="Username" value={form.username} onChange={handleChange} />
          <input name="password" type="password" placeholder="Password" value={form.password} onChange={handleChange} />

          {error && <div className="error-box">{error}</div>}

          <button type="submit" className="primary-btn full-width" disabled={loading}>
            {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Auth;
