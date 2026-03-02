// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Menu, X } from 'lucide-react';
import { Logo } from '../logo/logo';
import { Button } from '../atoms/button/button';

export function Header() {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    return (
        <header className="sticky top-0 z-30 border-b border-border bg-white shadow-sm dark:bg-background">
            <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4 sm:px-6 lg:px-8">
                {/* Logo + Brand */}
                <Link to="/" className="flex items-center gap-2">
                    <Logo />
                    <span className="font-display text-base font-bold text-[#1e3a5f] dark:text-foreground">
                        Summit Cap Financial
                    </span>
                </Link>

                {/* Right side actions */}
                <div className="flex items-center gap-2">
                    <div className="hidden items-center gap-2 md:flex">
                        <Button
                            asChild
                            className="bg-[#1e3a5f] text-white hover:bg-[#2b5a8f]"
                            size="sm"
                        >
                            <Link to={'/sign-in' as never}>Sign In</Link>
                        </Button>
                    </div>

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
                            <Button
                                asChild
                                className="w-full bg-[#1e3a5f] text-white hover:bg-[#2b5a8f]"
                                size="sm"
                            >
                                <Link to={'/sign-in' as never}>Sign In</Link>
                            </Button>
                        </div>
                    </nav>
                </div>
            )}
        </header>
    );
}
