// This project was developed with assistance from AI tools.

import { createFileRoute, Outlet, useNavigate, useLocation } from '@tanstack/react-router';
import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth, type UserRole } from '@/contexts/auth-context';
import { ChatSidebar } from '@/components/organisms/chat-sidebar/chat-sidebar';

const ROLE_HOME: Record<UserRole, string> = {
    prospect: '/sign-in',
    borrower: '/borrower',
    loan_officer: '/loan-officer',
    underwriter: '/underwriter',
    ceo: '/executive',
};

/** Check if the current path is allowed for the user's role. */
function isRouteAllowed(pathname: string, role: UserRole): boolean {
    if (pathname.startsWith('/borrower')) return role === 'borrower';
    if (pathname.startsWith('/loan-officer')) return role === 'loan_officer';
    if (pathname.startsWith('/underwriter')) return role === 'underwriter';
    if (pathname.startsWith('/executive')) return role === 'ceo';
    if (pathname.startsWith('/ceo')) return role === 'ceo';
    return true; // root or unknown routes
}

export const Route = createFileRoute('/_authenticated')({
    component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
    const { user, isAuthenticated, isInitializing } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        if (isInitializing) return;
        if (!isAuthenticated) {
            navigate({ to: '/sign-in' as never });
            return;
        }
        // Role-based redirect: prevent cross-role route access
        if (user && !isRouteAllowed(location.pathname, user.role)) {
            navigate({ to: (ROLE_HOME[user.role] ?? '/') as never });
        }
    }, [isAuthenticated, isInitializing, navigate, user, location.pathname]);

    if (isInitializing) {
        return (
            <div className="flex flex-1 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-[#1e3a5f]" />
            </div>
        );
    }

    if (!isAuthenticated) {
        return null;
    }

    return (
        <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 overflow-y-auto lg:pr-[340px]">
                <Outlet />
            </main>
            <ChatSidebar />
        </div>
    );
}
