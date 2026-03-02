// This project was developed with assistance from AI tools.

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface ChatContextValue {
    isOpen: boolean;
    initialMessage: string | null;
    openChat: (message?: string) => void;
    closeChat: () => void;
    clearInitialMessage: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
    const [isOpen, setIsOpen] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);

    const openChat = useCallback((message?: string) => {
        if (message) setInitialMessage(message);
        setIsOpen(true);
    }, []);

    const closeChat = useCallback(() => {
        setIsOpen(false);
    }, []);

    const clearInitialMessage = useCallback(() => {
        setInitialMessage(null);
    }, []);

    return (
        <ChatContext.Provider value={{ isOpen, initialMessage, openChat, closeChat, clearInitialMessage }}>
            {children}
        </ChatContext.Provider>
    );
}

export function useChatContext(): ChatContextValue {
    const ctx = useContext(ChatContext);
    if (!ctx) throw new Error('useChatContext must be used within ChatProvider');
    return ctx;
}
