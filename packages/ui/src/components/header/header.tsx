// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Menu, X, LogOut } from 'lucide-react';
import { Logo } from '../logo/logo';
import { Button } from '../atoms/button/button';
import { useAuth, type UserRole } from '@/contexts/auth-context';
import { cn } from '@/lib/utils';

const ROLE_BADGE_STYLES: Record<UserRole, string> = {
    prospect: 'bg-slate-100 text-slate-700',
    borrower: 'bg-emerald-100 text-emerald-700',
    loan_officer: 'bg-purple-100 text-purple-700',
    underwriter: 'bg-orange-100 text-orange-700',
    ceo: 'bg-[#1e3a5f]/10 text-[#1e3a5f]',
};

const ROLE_LABELS: Record<UserRole, string> = {
    prospect: 'Prospect',
    borrower: 'Borrower',
    loan_officer: 'Loan Officer',
    underwriter: 'Underwriter',
    ceo: 'CEO',
};

export function Header() {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const { user, isAuthenticated, signOut } = useAuth();
    const navigate = useNavigate();

    function handleSignOut() {
        signOut();
        navigate({ to: '/' as never });
    }

    return (
        <header className="sticky top-0 z-30 border-b border-border bg-white shadow-sm dark:bg-background">
            <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-4 sm:px-6 lg:px-8">
                {/* Logo + Brand */}
                <Link to="/" className="flex items-center gap-2">
                    <Logo />
                    <span className="font-display text-base font-bold text-[#1e3a5f] dark:text-foreground">
                        Summit Cap Financial
                    </span>
                </Link>

                {/* Right side actions */}
                <div className="flex items-center gap-2">
                    {isAuthenticated && user ? (
                        <div className="hidden items-center gap-3 md:flex">
                            <span className="text-sm font-medium text-foreground">{user.name}</span>
                            <span
                                className={cn(
                                    'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                                    ROLE_BADGE_STYLES[user.role],
                                )}
                            >
                                {ROLE_LABELS[user.role]}
                            </span>
                            <button
                                onClick={handleSignOut}
                                className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground dark:hover:bg-white/10"
                                aria-label="Sign out"
                            >
                                <LogOut className="h-4 w-4" />
                                <span>Sign Out</span>
                            </button>
                        </div>
                    ) : (
                        <div className="hidden items-center gap-2 md:flex">
                            <Button
                                asChild
                                className="bg-[#1e3a5f] text-white hover:bg-[#2b5a8f]"
                                size="sm"
                            >
                                <Link to={'/sign-in' as never}>Sign In</Link>
                            </Button>
                        </div>
                    )}

                    {/* Mobile hamburger */}
                    <button
                        type="button"
                        className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
                        aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
                        aria-expanded={isMobileMenuOpen}
                        onClick={() => setIsMobileMenuOpen((prev) => !prev)}
                    >
                        {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </button>
                </div>
            </div>

            {/* Mobile menu panel */}
            {isMobileMenuOpen && (
                <div className="border-t border-border bg-white px-4 pb-4 dark:bg-background md:hidden">
                    <nav className="flex flex-col gap-1 pt-2" aria-label="Mobile navigation">
                        <div className="mt-2 flex flex-col gap-2">
                            {isAuthenticated && user ? (
                                <>
                                    <div className="flex items-center gap-2 px-1 py-2">
                                        <span className="text-sm font-medium text-foreground">
                                            {user.name}
                                        </span>
                                        <span
                                            className={cn(
                                                'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                                                ROLE_BADGE_STYLES[user.role],
                                            )}
                                        >
                                            {ROLE_LABELS[user.role]}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => {
                                            handleSignOut();
                                            setIsMobileMenuOpen(false);
                                        }}
                                        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground"
                                    >
                                        <LogOut className="h-4 w-4" />
                                        Sign Out
                                    </button>
                                </>
                            ) : (
                                <Button
                                    asChild
                                    className="w-full bg-[#1e3a5f] text-white hover:bg-[#2b5a8f]"
                                    size="sm"
                                >
                                    <Link to={'/sign-in' as never}>Sign In</Link>
                                </Button>
                            )}
                        </div>
                    </nav>
                </div>
            )}
        </header>
    );
}
