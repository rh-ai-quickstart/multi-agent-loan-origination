// This project was developed with assistance from AI tools.

import { useEffect } from 'react';
import { useAuth } from './auth-context';
import { setAuthHeaderProvider } from '@/lib/api-client';

export function AuthHeaderSync() {
    const { apiHeaders } = useAuth();

    useEffect(() => {
        setAuthHeaderProvider(apiHeaders);
    }, [apiHeaders]);

    return null;
}
