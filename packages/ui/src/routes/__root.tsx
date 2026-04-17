// This project was developed with assistance from AI tools.

import { createRootRoute, Outlet, useMatchRoute } from '@tanstack/react-router';
import { Header } from '../components/header/header';
import { Footer } from '../components/footer/footer';
import { ChatPanel, ChatFab } from '../components/organisms/chat-panel/chat-panel';
import { ChatProvider, useChatContext } from '../contexts/chat-context';
import { useAuth } from '../contexts/auth-context';

export const Route = createRootRoute({
    component: RootLayout,
});

function RootLayoutInner() {
    const { isOpen, openChat } = useChatContext();
    const { isAuthenticated } = useAuth();
    const matchRoute = useMatchRoute();
    const isFullscreen = !!matchRoute({ to: '/sign-in' as never });

    if (isFullscreen) {
        return <Outlet />;
    }

    // Authenticated routes get their own chat sidebar via _authenticated layout
    const showPublicChat = !isAuthenticated;

    return (
        <div className={`flex flex-col ${isAuthenticated ? 'h-screen overflow-hidden' : 'min-h-screen'}`}>
            <Header />
            <main className={`flex-1 ${isAuthenticated ? 'overflow-hidden' : ''}`}>
                <Outlet />
            </main>
            {showPublicChat && <Footer />}
            {showPublicChat && !isOpen && <ChatFab onClick={() => openChat()} />}
            {showPublicChat && <ChatPanel />}
        </div>
    );
}

function RootLayout() {
    return (
        <ChatProvider>
            <RootLayoutInner />
        </ChatProvider>
    );
}
