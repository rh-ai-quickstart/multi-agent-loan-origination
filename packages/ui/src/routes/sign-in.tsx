// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Eye, EyeOff, X, Home, Briefcase, ClipboardCheck, BarChart3, Loader2 } from 'lucide-react';
import { Logo } from '../components/logo/logo';
import { useAuth, DEV_USERS, type UserRole } from '../contexts/auth-context';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const Route = createFileRoute('/sign-in' as any)({
    component: SignIn,
});

const PERSONAS: {
    role: UserRole;
    label: string;
    icon: typeof Home;
    bg: string;
    text: string;
    hoverBg: string;
}[] = [
    { role: 'borrower', label: 'Borrower', icon: Home, bg: 'bg-green-100', text: 'text-green-700', hoverBg: 'hover:bg-green-200' },
    { role: 'loan_officer', label: 'Loan Officer', icon: Briefcase, bg: 'bg-purple-100', text: 'text-purple-700', hoverBg: 'hover:bg-purple-200' },
    { role: 'underwriter', label: 'Underwriter', icon: ClipboardCheck, bg: 'bg-orange-100', text: 'text-orange-700', hoverBg: 'hover:bg-orange-200' },
    { role: 'ceo', label: 'CEO', icon: BarChart3, bg: 'bg-[#1e3a5f]/10', text: 'text-[#1e3a5f]', hoverBg: 'hover:bg-[#1e3a5f]/20' },
];

const ROLE_REDIRECTS: Record<UserRole, string> = {
    prospect: '/',
    borrower: '/borrower',
    loan_officer: '/loan-officer',
    underwriter: '/underwriter',
    ceo: '/ceo',
};

function SignIn() {
    const { signInWithCredentials } = useAuth();
    const navigate = useNavigate();
    const [showPassword, setShowPassword] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    function handlePersonaClick(role: UserRole) {
        const user = DEV_USERS[role];
        setEmail(user.email);
        setPassword('demo1234');
        setError(null);
    }

    async function handleSignIn(e: React.FormEvent) {
        e.preventDefault();
        setError(null);
        setIsLoading(true);
        try {
            await signInWithCredentials(email, password);
            const match = Object.values(DEV_USERS).find((u) => u.email === email);
            const redirect = match ? ROLE_REDIRECTS[match.role] : '/';
            navigate({ to: redirect as never });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Sign in failed');
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <div className="flex min-h-screen w-full items-stretch bg-white dark:bg-background">
            {/* Left side: image + hero text -- flows to left edge */}
            <div className="relative hidden flex-1 flex-col justify-end overflow-hidden bg-[#1e3a5f] lg:flex">
                <div
                    className="absolute inset-0 z-0 bg-cover bg-center opacity-40 mix-blend-overlay"
                    style={{ backgroundImage: 'url("/sign-in-bg.png")' }}
                />
                <div className="absolute inset-0 z-10 bg-gradient-to-t from-[#1e3a5f] via-[#1e3a5f]/60 to-transparent" />
                <div className="relative z-20 flex flex-col gap-6 p-16">
                    <h1 className="max-w-2xl font-display text-5xl font-black leading-tight tracking-tight text-white drop-shadow-md">
                        Empowering your homeownership journey with AI-driven insights.
                    </h1>
                    <p className="max-w-xl text-lg text-slate-200">
                        Join thousands of homeowners who have unlocked better rates and faster
                        closings with our intelligent platform.
                    </p>
                </div>
            </div>

            {/* Right side: sign-in form */}
            <div className="flex w-full flex-col items-center justify-center px-6 py-12 lg:w-[480px] lg:shrink-0">
                <div className="w-full max-w-[400px] rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-background sm:p-10">
                    {/* Logo + Close */}
                    <div className="mb-10 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Logo />
                            <span className="text-xl font-bold tracking-tight text-[#1e3a5f] dark:text-foreground">
                                Summit Cap Financial
                            </span>
                        </div>
                        <button
                            type="button"
                            onClick={() => navigate({ to: '/' as never })}
                            className="flex h-10 w-10 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-white/10 dark:hover:text-white"
                            aria-label="Return to home"
                        >
                            <X className="h-6 w-6" />
                        </button>
                    </div>

                    <div className="flex flex-col gap-8">
                        {/* Heading */}
                        <div>
                            <h2 className="text-3xl font-bold tracking-tight text-foreground">
                                Sign In
                            </h2>
                            <p className="mt-2 text-muted-foreground">
                                Access your mortgage dashboard to manage your loans.
                            </p>
                        </div>

                        <form
                            onSubmit={handleSignIn}
                            className="flex flex-col gap-5"
                        >
                            <div className="relative">
                                <input
                                    id="email"
                                    type="email"
                                    placeholder="Email Address"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="block w-full rounded-lg border border-slate-300 bg-transparent px-4 py-3.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-[#1e3a5f] focus:outline-none focus:ring-1 focus:ring-[#1e3a5f] dark:border-slate-600"
                                />
                            </div>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    placeholder="Password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="block w-full rounded-lg border border-slate-300 bg-transparent px-4 py-3.5 pr-12 text-sm text-foreground placeholder:text-muted-foreground focus:border-[#1e3a5f] focus:outline-none focus:ring-1 focus:ring-[#1e3a5f] dark:border-slate-600"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword((p) => !p)}
                                    className="absolute right-3 top-3.5 text-muted-foreground hover:text-[#1e3a5f]"
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                >
                                    {showPassword ? (
                                        <Eye className="h-5 w-5" />
                                    ) : (
                                        <EyeOff className="h-5 w-5" />
                                    )}
                                </button>
                            </div>

                            <div className="flex items-center justify-between">
                                <label className="flex cursor-pointer items-center gap-2">
                                    <input
                                        type="checkbox"
                                        className="h-4 w-4 rounded border-slate-300 text-[#1e3a5f] focus:ring-[#1e3a5f]"
                                    />
                                    <span className="text-sm text-muted-foreground">
                                        Remember me
                                    </span>
                                </label>
                                <button
                                    type="button"
                                    className="text-sm font-semibold text-[#1e3a5f] hover:underline dark:text-blue-400"
                                >
                                    Forgot Password?
                                </button>
                            </div>

                            {error && (
                                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                                    {error}
                                </p>
                            )}

                            <button
                                type="submit"
                                disabled={isLoading}
                                className="flex h-12 w-full items-center justify-center rounded-lg bg-[#1e3a5f] text-base font-bold text-white shadow-lg shadow-[#1e3a5f]/30 transition hover:bg-[#152e42] focus:outline-none focus:ring-2 focus:ring-[#1e3a5f] focus:ring-offset-2 disabled:opacity-60"
                            >
                                {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Sign In'}
                            </button>
                        </form>

                        {/* Persona demo login */}
                        <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-6 dark:border-white/10 dark:bg-white/5">
                            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                Persona Demo Login
                            </p>
                            <div className="grid grid-cols-4 gap-2">
                                {PERSONAS.map(({ role, label, icon: Icon, bg, text, hoverBg }) => (
                                    <button
                                        key={role}
                                        type="button"
                                        onClick={() => handlePersonaClick(role)}
                                        className="group flex flex-col items-center gap-2 rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-white/10"
                                        title={label}
                                    >
                                        <div
                                            className={`flex h-10 w-10 items-center justify-center rounded-full transition ${bg} ${text} ${hoverBg}`}
                                        >
                                            <Icon className="h-5 w-5" />
                                        </div>
                                        <span className="text-[10px] font-medium text-muted-foreground">
                                            {label}
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
