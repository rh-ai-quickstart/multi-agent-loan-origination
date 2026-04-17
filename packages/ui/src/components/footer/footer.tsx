// This project was developed with assistance from AI tools.

import { Logo } from '../logo/logo';
import { COMPANY_NAME } from '@/lib/company';

export function Footer() {
    return (
        <footer className="w-full bg-[#1e3a5f] text-white dark:bg-black">
            <div className="mx-auto max-w-[1200px] px-4 py-12 sm:px-6 lg:px-8">
                <div className="flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
                    {/* Brand */}
                    <div className="flex items-center gap-2">
                        <Logo />
                        <span className="font-display text-base font-bold">{COMPANY_NAME}</span>
                    </div>

                    {/* Section links */}
                    <div className="flex gap-8">
                        <span className="text-sm font-semibold uppercase tracking-widest text-white/50">Products</span>
                        <span className="text-sm font-semibold uppercase tracking-widest text-white/50">Company</span>
                        <span className="text-sm font-semibold uppercase tracking-widest text-white/50">Support</span>
                    </div>
                </div>

                {/* Bottom bar */}
                <div className="mt-10 border-t border-white/10 pt-8 text-xs text-white/50">
                    <p className="italic">
                        This organization, its activities and its employees are fictional and are
                        not intended to represent or depict any current or former business
                        organization or any individuals. Any resemblance to any individual or
                        organization is purely coincidental.
                    </p>
                </div>
            </div>
        </footer>
    );
}
