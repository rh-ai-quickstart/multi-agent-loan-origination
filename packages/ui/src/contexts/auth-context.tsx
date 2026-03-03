// This project was developed with assistance from AI tools.
/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { setAuthHeaderProvider } from '@/lib/api-client';

export type UserRole = 'prospect' | 'borrower' | 'loan_officer' | 'underwriter' | 'ceo';

export interface DevUser {
    role: UserRole;
    user_id: string;
    name: string;
    email: string;
}

export const DEV_USERS: Record<UserRole, DevUser> = {
    prospect: {
        role: 'prospect',
        user_id: 'dev-prospect',
        name: 'Guest Visitor',
        email: 'prospect@dev.summitcap.local',
    },
    borrower: {
        role: 'borrower',
        user_id: 'dev-borrower-1',
        name: 'Maria Garcia',
        email: 'maria.garcia@dev.summitcap.local',
    },
    loan_officer: {
        role: 'loan_officer',
        user_id: 'dev-lo-1',
        name: 'James Chen',
        email: 'james.chen@dev.summitcap.local',
    },
    underwriter: {
        role: 'underwriter',
        user_id: 'dev-uw-1',
        name: 'Sarah Mitchell',
        email: 'sarah.mitchell@dev.summitcap.local',
    },
    ceo: {
        role: 'ceo',
        user_id: 'dev-ceo-1',
        name: 'Robert Taylor',
        email: 'robert.taylor@dev.summitcap.local',
    },
};

const STORAGE_KEY = 'summit-cap-dev-role';
const TOKEN_KEY = 'summit-cap-token';

const ROLE_CHAT_PATHS: Record<UserRole, string> = {
    prospect: '/api/chat',
    borrower: '/api/borrower/chat',
    loan_officer: '/api/loan-officer/chat',
    underwriter: '/api/underwriter/chat',
    ceo: '/api/ceo/chat',
};

interface AuthContextValue {
    user: DevUser | null;
    token: string | null;
    isAuthenticated: boolean;
    chatPath: string;
    signIn: (role: UserRole) => void;
    signInWithCredentials: (email: string, password: string) => Promise<void>;
    signOut: () => void;
    apiHeaders: () => Record<string, string>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredRole(): UserRole | null {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && stored in DEV_USERS) {
            return stored as UserRole;
        }
    } catch {
        // localStorage unavailable (SSR or privacy mode)
    }
    return null;
}

function loadStoredToken(): string | null {
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch {
        return null;
    }
}

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<DevUser | null>(() => {
        const role = loadStoredRole();
        return role ? DEV_USERS[role] : null;
    });
    const [token, setToken] = useState<string | null>(loadStoredToken);

    const signIn = useCallback((role: UserRole) => {
        const devUser = DEV_USERS[role];
        setUser(devUser);
        try {
            localStorage.setItem(STORAGE_KEY, role);
        } catch {
            // localStorage unavailable
        }
    }, []);

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const signInWithCredentials = useCallback(async (email: string, _password: string) => {
        // Dev mode: lookup DEV_USERS by email
        const match = Object.values(DEV_USERS).find((u) => u.email === email);
        if (!match) {
            throw new Error('Invalid email or password');
        }
        // In dev mode, just sign in with the matched role
        signIn(match.role);
        // When Keycloak is enabled, this would POST to the token endpoint:
        // const resp = await fetch('/auth/realms/summit-cap/protocol/openid-connect/token', { ... })
        // const { access_token } = await resp.json();
        // setToken(access_token);
        // localStorage.setItem(TOKEN_KEY, access_token);
    }, [signIn]);

    const signOut = useCallback(() => {
        setUser(null);
        setToken(null);
        try {
            localStorage.removeItem(STORAGE_KEY);
            localStorage.removeItem(TOKEN_KEY);
        } catch {
            // localStorage unavailable
        }
    }, []);

    const apiHeaders = useCallback((): Record<string, string> => {
        if (token) {
            return { Authorization: `Bearer ${token}` };
        }
        if (!user) return {};
        return {
            'X-Dev-Role': user.role,
            'X-Dev-User-Id': user.user_id,
            'X-Dev-User-Email': user.email,
            'X-Dev-User-Name': user.name,
        };
    }, [user, token]);

    // Keep the API client auth header provider in sync
    useEffect(() => {
        setAuthHeaderProvider(apiHeaders);
    }, [apiHeaders]);

    const chatPath = user ? ROLE_CHAT_PATHS[user.role] : '/api/chat';

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isAuthenticated: user !== null && user.role !== 'prospect',
                chatPath,
                signIn,
                signInWithCredentials,
                signOut,
                apiHeaders,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return ctx;
}
