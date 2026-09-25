import { useState, type FormEvent } from 'react';
import { apiRequest, type AuthUser } from './api';
import Icon from './Icon';

type Mode = 'login' | 'register' | 'reset';
type Props = { onAuthenticated: (user: AuthUser) => void; apiError: string | null };

export default function AuthScreen({ onAuthenticated, apiError }: Props) {
  const [mode, setMode] = useState<Mode>('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      if (mode === 'reset') {
        await apiRequest('/api/v1/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email: form.email }) });
        setMessage('If an account exists, check your email for reset instructions.');
      } else {
        const user = await apiRequest<AuthUser>(mode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register', { method: 'POST', body: JSON.stringify(form) });
        onAuthenticated(user);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to authenticate right now.'); }
    finally { setBusy(false); }
  };
  const switchMode = (next: Mode) => { setMode(next); setError(''); setMessage(''); setForm((current) => ({ ...current, password: '' })); };
  return <main className="auth-page"><div className="auth-decoration decoration-one" /><div className="auth-decoration decoration-two" /><section className="auth-card"><div className="auth-brand"><div className="brand-mark" /><span>adpilot</span></div><div className="auth-copy"><p className="eyebrow">Your advertising copilot</p><h1>{mode === 'login' ? 'Welcome back.' : mode === 'register' ? 'Start making ads smarter.' : 'Reset your password.'}</h1><p>{mode === 'login' ? 'Sign in to keep your campaigns moving.' : mode === 'register' ? 'Create your workspace and turn one brief into every channel.' : 'Enter your email and we will send reset instructions.'}</p></div><div className="auth-tabs">{mode !== 'reset' && <><button className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>Sign in</button><button className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>Create account</button></>}</div>{(error || apiError) && <div className="auth-message error" role="alert">{error || apiError}</div>}{message && <div className="auth-message success" role="status">{message}</div>}<form className="auth-form" onSubmit={submit}>{mode === 'register' && <label>Full name<input required autoComplete="name" value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Alex Morgan" /></label>}<label>Email address<input required type="email" autoComplete="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="you@company.com" /></label>{mode !== 'reset' && <label>Password<input required minLength={8} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={form.password} onChange={(event) => update('password', event.target.value)} placeholder="At least 8 characters" /></label>}<button className="button button-primary auth-submit" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in to AdPilot' : mode === 'register' ? 'Create my workspace' : 'Send reset instructions'}{!busy && <Icon name="arrow" size={16} />}</button></form><div className="auth-footer">{mode === 'login' ? <><span>New to AdPilot?</span><button onClick={() => switchMode('register')}>Create an account</button></> : mode === 'register' ? <><span>Already have an account?</span><button onClick={() => switchMode('login')}>Sign in</button></> : <button onClick={() => switchMode('login')}>Back to sign in</button>}</div>{mode === 'login' && <button className="forgot-link" onClick={() => switchMode('reset')}>Forgot your password?</button>}<p className="auth-legal">By continuing, you agree to AdPilot’s terms and privacy policy.</p></section><aside className="auth-aside"><div className="auth-aside-top"><span className="aside-pill"><i />Built for modern marketers</span><h2>One brief.<br /><em>Every channel.</em></h2><p>Create once, adapt everywhere, and stay in control of every publishing decision.</p></div><div className="auth-preview"><div className="preview-header"><span>Campaign performance</span><b>Last 30 days</b></div><div className="preview-number">$1,932.80 <small>+18.4%</small></div><div className="preview-bars"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div><div className="preview-footer"><span><b>284K</b> impressions</span><span><b>327</b> conversions</span></div></div><div className="auth-quote"><p>“AdPilot gives our small team the confidence to run campaigns like an agency.”</p><span>— Maya Chen, Growth Lead</span></div></aside></main>;
}
