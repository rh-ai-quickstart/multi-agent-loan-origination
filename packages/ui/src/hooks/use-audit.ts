// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchAuditEvents, fetchAuditEventsFiltered } from '@/services/audit';

export function useAuditEvents(limit: number) {
    return useQuery({
        queryKey: ['audit', 'events', limit],
        queryFn: () => fetchAuditEvents(limit),
    });
}

export function useAuditEventsFiltered(days: number, eventType: string, limit: number) {
    return useQuery({
        queryKey: ['audit', 'events', 'filtered', days, eventType, limit],
        queryFn: () => fetchAuditEventsFiltered({ days, eventType: eventType || undefined, limit }),
    });
}
