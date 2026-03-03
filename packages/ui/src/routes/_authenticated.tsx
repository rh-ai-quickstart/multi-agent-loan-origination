// This project was developed with assistance from AI tools.

import { createFileRoute, Outlet, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { ChatSidebar } from '@/components/organisms/chat-sidebar/chat-sidebar';


export const Route = createFileRoute('/_authenticated')({
    component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
    const { isAuthenticated, isInitializing } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (isInitializing) return;
        if (!isAuthenticated) {
            navigate({ to: '/sign-in' as never });
        }
    }, [isAuthenticated, isInitializing, navigate]);

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
