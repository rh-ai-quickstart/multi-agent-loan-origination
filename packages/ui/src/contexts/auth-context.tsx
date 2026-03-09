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

// Dev user IDs must match config/keycloak/mortgage-ai-realm.json and seed fixtures
export const DEV_USERS: Record<UserRole, AuthUser> = {
    prospect: {
        role: 'prospect',
        user_id: 'dev-prospect',
        name: 'Guest Visitor',
        email: 'prospect@example.com',
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
        email: 'james.torres@example.com',
    },
    underwriter: {
        role: 'underwriter',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567803',
        name: 'Maria Chen',
        email: 'maria.chen@example.com',
    },
    ceo: {
        role: 'ceo',
        user_id: 'd1a2b3c4-e5f6-7890-abcd-ef1234567804',
        name: 'David Park',
        email: 'david.park@example.com',
    },
};

const STORAGE_KEY = 'mortgage-ai-dev-role';
const KC_AUTH_KEY = 'mortgage-ai-kc-auth';

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

// Keycloak config: runtime config (container) takes precedence over Vite env (local dev)
const _rtc = (window as unknown as Record<string, unknown>).__RUNTIME_CONFIG__ as
    | { KEYCLOAK_URL?: string; KEYCLOAK_REALM?: string; KEYCLOAK_CLIENT_ID?: string }
    | undefined;
const KEYCLOAK_URL = _rtc?.KEYCLOAK_URL || (import.meta.env.VITE_KEYCLOAK_URL as string | undefined) || undefined;
const KEYCLOAK_REALM = _rtc?.KEYCLOAK_REALM || (import.meta.env.VITE_KEYCLOAK_REALM as string) || 'mortgage-ai';
const KEYCLOAK_CLIENT_ID = _rtc?.KEYCLOAK_CLIENT_ID || (import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string) || 'mortgage-ai-ui';
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

interface StoredKcAuth {
    access_token: string;
    refresh_token?: string;
    user: AuthUser;
    exp?: number;
}

function storeKcAuth(data: StoredKcAuth): void {
    try {
        localStorage.setItem(KC_AUTH_KEY, JSON.stringify(data));
    } catch {
        // localStorage unavailable
    }
}

function loadStoredKcAuth(): StoredKcAuth | null {
    try {
        const raw = localStorage.getItem(KC_AUTH_KEY);
        if (!raw) return null;
        const data = JSON.parse(raw) as StoredKcAuth;
        // Skip expired tokens (with 30s buffer)
        if (data.exp && data.exp * 1000 < Date.now() + 30_000) return null;
        return data;
    } catch {
        return null;
    }
}

function clearKcAuth(): void {
    try {
        localStorage.removeItem(KC_AUTH_KEY);
    } catch {
        // localStorage unavailable
    }
}

/** Decode a JWT payload with proper base64url handling (RFC 7515). */
function decodeJwtPayload(token: string): Record<string, unknown> {
    const payload = token.split('.')[1];
    if (!payload) throw new Error('Malformed JWT');
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(padded));
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

        // Restore ROPC session from localStorage (survives page reload and
        // Playwright storageState capture for e2e tests).
        const stored = loadStoredKcAuth();
        if (stored) {
            setToken(stored.access_token);
            setUser(stored.user);

            // Schedule refresh if we have a refresh_token
            if (stored.refresh_token) {
                const msUntilExpiry = stored.exp ? stored.exp * 1000 - Date.now() : 840_000;
                const refreshIn = Math.max(msUntilExpiry - 60_000, 10_000);
                const tokenUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
                if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
                const doRefresh = (rt: string) => {
                    fetch(tokenUrl, {
                        method: 'POST',
                        body: new URLSearchParams({
                            grant_type: 'refresh_token',
                            client_id: KEYCLOAK_CLIENT_ID,
                            refresh_token: rt,
                        }),
                    })
                        .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Refresh failed'))))
                        .then((d) => {
                            const newAccess = d.access_token as string;
                            const newRefresh = (d.refresh_token as string) || rt;
                            setToken(newAccess);
                            const newClaims = decodeJwtPayload(newAccess);
                            const roles = ((newClaims.realm_access as Record<string, unknown>)?.roles as string[]) ?? [];
                            const roleMatch = roles.find((r2) => KNOWN_ROLES.has(r2));
                            const role: UserRole = roleMatch === 'admin' ? 'ceo' : (roleMatch as UserRole) ?? 'borrower';
                            const newUser: AuthUser = {
                                role,
                                user_id: (newClaims.sub as string) ?? '',
                                name: (newClaims.name as string) ?? (newClaims.preferred_username as string) ?? '',
                                email: (newClaims.email as string) ?? '',
                            };
                            setUser(newUser);
                            const newExp = newClaims.exp as number | undefined;
                            storeKcAuth({ access_token: newAccess, refresh_token: newRefresh, user: newUser, exp: newExp });
                            const nextMs = newExp ? Math.max(newExp * 1000 - Date.now() - 60_000, 10_000) : 840_000;
                            refreshTimerRef.current = setTimeout(() => doRefresh(newRefresh), nextMs);
                        })
                        .catch(() => {
                            setUser(null);
                            setToken(null);
                            clearKcAuth();
                        });
                };
                refreshTimerRef.current = setTimeout(() => doRefresh(stored.refresh_token!), refreshIn);
            }

            setIsInitializing(false);
            return () => {
                if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
            };
        }

        // No stored ROPC session -- fall back to keycloak-js check-sso
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
                // NOTE: Direct access grant (ROPC) is used for MVP demo convenience.
                // ROPC is deprecated in OAuth 2.1. For production, switch to
                // Authorization Code + PKCE flow (already configured on the client).
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
                const refreshToken = data.refresh_token as string | undefined;
                setToken(accessToken);

                // Decode claims using base64url-safe decode
                const claims = decodeJwtPayload(accessToken);
                const roles = ((claims.realm_access as Record<string, unknown>)?.roles as string[]) ?? [];
                const roleMatch = roles.find((r) => KNOWN_ROLES.has(r));
                const role: UserRole = roleMatch === 'admin' ? 'ceo' : (roleMatch as UserRole) ?? 'borrower';
                const authUser: AuthUser = {
                    role,
                    user_id: (claims.sub as string) ?? '',
                    name: (claims.name as string) ?? (claims.preferred_username as string) ?? '',
                    email: (claims.email as string) ?? '',
                };
                setUser(authUser);

                // Persist to localStorage (survives page reload + Playwright storageState)
                storeKcAuth({
                    access_token: accessToken,
                    refresh_token: refreshToken,
                    user: authUser,
                    exp: claims.exp as number | undefined,
                });

                // Schedule token refresh using the refresh_token from ROPC response
                if (refreshToken) {
                    const exp = claims.exp as number | undefined;
                    const msUntilExpiry = exp ? exp * 1000 - Date.now() : 840_000;
                    const refreshIn = Math.max(msUntilExpiry - 60_000, 10_000);
                    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
                    const doRefresh = () => {
                        fetch(tokenUrl, {
                            method: 'POST',
                            body: new URLSearchParams({
                                grant_type: 'refresh_token',
                                client_id: KEYCLOAK_CLIENT_ID,
                                refresh_token: refreshToken,
                            }),
                        })
                            .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Refresh failed'))))
                            .then((d) => {
                                const newAccess = d.access_token as string;
                                setToken(newAccess);
                                const newClaims = decodeJwtPayload(newAccess);
                                const newExp = newClaims.exp as number | undefined;
                                const newRoles = ((newClaims.realm_access as Record<string, unknown>)?.roles as string[]) ?? [];
                                const newRoleMatch = newRoles.find((r2) => KNOWN_ROLES.has(r2));
                                const newRole: UserRole = newRoleMatch === 'admin' ? 'ceo' : (newRoleMatch as UserRole) ?? 'borrower';
                                const newUser: AuthUser = {
                                    role: newRole,
                                    user_id: (newClaims.sub as string) ?? '',
                                    name: (newClaims.name as string) ?? (newClaims.preferred_username as string) ?? '',
                                    email: (newClaims.email as string) ?? '',
                                };
                                setUser(newUser);
                                storeKcAuth({ access_token: newAccess, refresh_token: refreshToken, user: newUser, exp: newExp });
                                const nextMs = newExp ? Math.max(newExp * 1000 - Date.now() - 60_000, 10_000) : 840_000;
                                refreshTimerRef.current = setTimeout(doRefresh, nextMs);
                            })
                            .catch(() => {
                                setUser(null);
                                setToken(null);
                                clearKcAuth();
                            });
                    };
                    refreshTimerRef.current = setTimeout(doRefresh, refreshIn);
                }
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
        clearKcAuth();
        if (IS_KEYCLOAK_ENABLED && keycloakRef.current) {
            keycloakRef.current.logout({ redirectUri: window.location.origin });
            return;
        }
        if (IS_KEYCLOAK_ENABLED) {
            // ROPC session (no keycloak-js adapter) -- clear and redirect
            setUser(null);
            setToken(null);
            window.location.href = window.location.origin;
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
