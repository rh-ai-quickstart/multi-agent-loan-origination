// Summit Cap Financial - Root Route
// This project was developed with assistance from AI tools.

import { createRootRoute, Outlet } from '@tanstack/react-router';
import { Header } from '../components/header/header';
import { Footer } from '../components/footer/footer';
import { ChatPanel, ChatFab } from '../components/organisms/chat-panel/chat-panel';
import { ChatProvider, useChatContext } from '../contexts/chat-context';

export const Route = createRootRoute({
    component: RootLayout,
});

function RootLayoutInner() {
    const { isOpen, openChat } = useChatContext();

    return (
        <div className="flex min-h-screen flex-col">
            <Header />
            <main className="flex-1">
                <Outlet />
            </main>
            <Footer />
            {!isOpen && <ChatFab onClick={() => openChat()} />}
            <ChatPanel />
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
