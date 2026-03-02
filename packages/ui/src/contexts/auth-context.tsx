// This project was developed with assistance from AI tools.

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

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

interface AuthContextValue {
    user: DevUser | null;
    isAuthenticated: boolean;
    signIn: (role: UserRole) => void;
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

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<DevUser | null>(() => {
        const role = loadStoredRole();
        return role ? DEV_USERS[role] : null;
    });

    const signIn = useCallback((role: UserRole) => {
        const devUser = DEV_USERS[role];
        setUser(devUser);
        try {
            localStorage.setItem(STORAGE_KEY, role);
        } catch {
            // localStorage unavailable
        }
    }, []);

    const signOut = useCallback(() => {
        setUser(null);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // localStorage unavailable
        }
    }, []);

    const apiHeaders = useCallback((): Record<string, string> => {
        if (!user) return {};
        return {
            'X-Dev-Role': user.role,
            'X-Dev-User-Id': user.user_id,
            'X-Dev-User-Email': user.email,
            'X-Dev-User-Name': user.name,
        };
    }, [user]);

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: user !== null, signIn, signOut, apiHeaders }}>
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
