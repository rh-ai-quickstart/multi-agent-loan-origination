// This project was developed with assistance from AI tools.
/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import Keycloak from 'keycloak-js';
import { setAuthHeaderProvider } from '@/lib/api-client';

export type UserRole = 'prospect' | 'borrower' | 'loan_officer' | 'underwriter' | 'ceo';

export interface AuthUser {
    role: UserRole;
    user_id: string;
    name: string;
    email: string;
}

// Dev user IDs must match config/keycloak/summit-cap-realm.json and seed fixtures
export const DEV_USERS: Record<UserRole, AuthUser> = {
    prospect: {
        role: 'prospect',
        user_id: 'dev-prospect',
        name: 'Guest Visitor',
        email: 'prospect@dev.summitcap.local',
    },
    borrower: {
        role: 'borrower',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567801',
        name: 'Sarah Mitchell',
        email: 'sarah.mitchell@example.com',
    },
    loan_officer: {
        role: 'loan_officer',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567802',
        name: 'James Torres',
        email: 'james.torres@summit-cap.com',
    },
    underwriter: {
        role: 'underwriter',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567803',
        name: 'Maria Chen',
        email: 'maria.chen@summit-cap.com',
    },
    ceo: {
        role: 'ceo',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567804',
        name: 'David Park',
        email: 'david.park@summit-cap.com',
    },
};

const STORAGE_KEY = 'summit-cap-dev-role';

const ROLE_CHAT_PATHS: Record<UserRole, string> = {
    prospect: '/api/chat',
    borrower: '/api/borrower/chat',
    loan_officer: '/api/loan-officer/chat',
    underwriter: '/api/underwriter/chat',
    ceo: '/api/ceo/chat',
};

const ROLE_HISTORY_PATHS: Record<UserRole, string | null> = {
    prospect: null,
    borrower: '/api/borrower/conversations/history',
    loan_officer: '/api/loan-officer/conversations/history',
    underwriter: '/api/underwriter/conversations/history',
    ceo: '/api/ceo/conversations/history',
};

// Keycloak config from Vite env -- when VITE_KEYCLOAK_URL is set, real OIDC is used
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL as string | undefined;
const KEYCLOAK_REALM = (import.meta.env.VITE_KEYCLOAK_REALM as string) || 'summit-cap';
const KEYCLOAK_CLIENT_ID = (import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string) || 'summit-cap-ui';
const IS_KEYCLOAK_ENABLED = !!KEYCLOAK_URL;

const KNOWN_ROLES = new Set<string>(['borrower', 'loan_officer', 'underwriter', 'ceo', 'admin']);

interface AuthContextValue {
    user: AuthUser | null;
    token: string | null;
    isAuthenticated: boolean;
    isKeycloak: boolean;
    isInitializing: boolean;
    chatPath: string;
    historyPath: string | null;
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

function resolveRoleFromToken(keycloak: Keycloak): UserRole {
    const roles: string[] = keycloak.realmAccess?.roles ?? [];
    const match = roles.find((r) => KNOWN_ROLES.has(r));
    if (match === 'admin') return 'ceo';
    return (match as UserRole) ?? 'borrower';
}

function buildUserFromToken(keycloak: Keycloak): AuthUser {
    const parsed = keycloak.tokenParsed as Record<string, unknown> | undefined;
    const role = resolveRoleFromToken(keycloak);
    return {
        role,
        user_id: keycloak.subject ?? '',
        name: (parsed?.name as string) ?? (parsed?.preferred_username as string) ?? '',
        email: (parsed?.email as string) ?? '',
    };
}

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<AuthUser | null>(() => {
        if (IS_KEYCLOAK_ENABLED) return null;
        const role = loadStoredRole();
        return role ? DEV_USERS[role] : null;
    });
    const [token, setToken] = useState<string | null>(null);
    const [isInitializing, setIsInitializing] = useState(IS_KEYCLOAK_ENABLED);
    const keycloakRef = useRef<Keycloak | null>(null);
    const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const initCalledRef = useRef(false);

    const scheduleRefresh = useCallback((kc: Keycloak) => {
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        const parsed = kc.tokenParsed as Record<string, unknown> | undefined;
        const exp = parsed?.exp as number | undefined;
        if (!exp) return;
        const msUntilExpiry = exp * 1000 - Date.now();
        // Refresh 60s before expiry, minimum 10s from now
        const refreshIn = Math.max(msUntilExpiry - 60_000, 10_000);
        refreshTimerRef.current = setTimeout(() => {
            kc.updateToken(30)
                .then((refreshed) => {
                    if (refreshed && kc.token) {
                        setToken(kc.token);
                        setUser(buildUserFromToken(kc));
                        scheduleRefresh(kc);
                    }
                })
                .catch(() => {
                    setUser(null);
                    setToken(null);
                });
        }, refreshIn);
    }, []);

    // ── Keycloak initialization (must run exactly once) ─────────────
    useEffect(() => {
        if (!IS_KEYCLOAK_ENABLED) return;
        if (initCalledRef.current) return;
        initCalledRef.current = true;

        const kc = new Keycloak({
            url: KEYCLOAK_URL!,
            realm: KEYCLOAK_REALM,
            clientId: KEYCLOAK_CLIENT_ID,
        });
        keycloakRef.current = kc;

        kc.init({
            onLoad: 'check-sso',
            silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
            pkceMethod: 'S256',
        })
            .then((authenticated) => {
                if (authenticated && kc.token) {
                    setToken(kc.token);
                    setUser(buildUserFromToken(kc));
                    scheduleRefresh(kc);
                }
                setIsInitializing(false);
            })
            .catch(() => {
                setIsInitializing(false);
            });

        kc.onTokenExpired = () => {
            kc.updateToken(30)
                .then((refreshed) => {
                    if (refreshed && kc.token) {
                        setToken(kc.token);
                        setUser(buildUserFromToken(kc));
                        scheduleRefresh(kc);
                    }
                })
                .catch(() => {
                    setUser(null);
                    setToken(null);
                });
        };

        return () => {
            if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        };
    }, [scheduleRefresh]);

    // ── Dev mode sign-in ─────────────────────────────────────────────
    const signIn = useCallback((role: UserRole) => {
        if (IS_KEYCLOAK_ENABLED) return;
        const devUser = DEV_USERS[role];
        setUser(devUser);
        try {
            localStorage.setItem(STORAGE_KEY, role);
        } catch {
            // localStorage unavailable
        }
    }, []);

    const signInWithCredentials = useCallback(
        async (email: string, password: string) => {
            if (IS_KEYCLOAK_ENABLED) {
                // Direct access grant (Resource Owner Password) against Keycloak token endpoint
                const tokenUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
                const body = new URLSearchParams({
                    grant_type: 'password',
                    client_id: KEYCLOAK_CLIENT_ID,
                    username: email,
                    password,
                    scope: 'openid',
                });
                const res = await fetch(tokenUrl, { method: 'POST', body });
                if (!res.ok) {
                    throw new Error('Invalid email or password');
                }
                const data = await res.json();
                const accessToken = data.access_token as string;
                setToken(accessToken);
                // Decode claims from the JWT payload
                const payloadB64 = accessToken.split('.')[1];
                const claims = JSON.parse(atob(payloadB64)) as Record<string, unknown>;
                const roles = ((claims.realm_access as Record<string, unknown>)?.roles as string[]) ?? [];
                const roleMatch = roles.find((r) => KNOWN_ROLES.has(r));
                const role: UserRole = roleMatch === 'admin' ? 'ceo' : (roleMatch as UserRole) ?? 'borrower';
                setUser({
                    role,
                    user_id: (claims.sub as string) ?? '',
                    name: (claims.name as string) ?? (claims.preferred_username as string) ?? '',
                    email: (claims.email as string) ?? '',
                });
                return;
            }
            // Dev mode: lookup DEV_USERS by email
            const match = Object.values(DEV_USERS).find((u) => u.email === email);
            if (!match) {
                throw new Error('Invalid email or password');
            }
            signIn(match.role);
        },
        [signIn],
    );

    const signOut = useCallback(() => {
        if (IS_KEYCLOAK_ENABLED && keycloakRef.current) {
            keycloakRef.current.logout({ redirectUri: window.location.origin });
            return;
        }
        setUser(null);
        setToken(null);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // localStorage unavailable
        }
    }, []);

    const apiHeaders = useCallback((): Record<string, string> => {
        if (token) {
            return { Authorization: `Bearer ${token}` };
        }
        if (!user) return {};
        // Dev mode: send dev headers
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
    const historyPath = user ? ROLE_HISTORY_PATHS[user.role] : null;

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isAuthenticated: user !== null && user.role !== 'prospect',
                isKeycloak: IS_KEYCLOAK_ENABLED,
                isInitializing,
                chatPath,
                historyPath,
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
