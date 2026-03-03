// This project was developed with assistance from AI tools.

import { createFileRoute, Outlet, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { ChatSidebar } from '@/components/organisms/chat-sidebar/chat-sidebar';

export const Route = createFileRoute('/_authenticated')({
    component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!isAuthenticated) {
            navigate({ to: '/' as never });
        }
    }, [isAuthenticated, navigate]);

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
