// This project was developed with assistance from AI tools.

// MVP: client-side lookup for staff display names. Keycloak user IDs are
// deterministic in the seed data so we can resolve them without an API call.
// In production this would be replaced by a user directory lookup.

export const STAFF_NAMES: Record<string, string> = {
    // CEO
    'd1a2b3c4-e5f6-7890-abcd-ef1234567801': 'Sarah Mitchell',
    // Loan Officers
    'd1a2b3c4-e5f6-7890-abcd-ef1234567802': 'James Torres',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567807': 'Sarah Patel',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567808': 'Marcus Williams',
    // Underwriters
    'd1a2b3c4-e5f6-7890-abcd-ef1234567803': 'Maria Chen',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567804': 'David Park',
    // Admin
    'd1a2b3c4-e5f6-7890-abcd-ef1234567805': 'Admin',
    // Borrowers
    'd1a2b3c4-e5f6-7890-abcd-ef1234567806': 'Jennifer Mitchell',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567811': 'Michael Johnson',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567812': 'Emily Rodriguez',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567813': 'Robert Kim',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567814': 'Lisa Washington',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567815': 'Thomas Nguyen',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567816': 'Amanda Foster',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567817': 'Daniel Ramirez',
    'd1a2b3c4-e5f6-7890-abcd-ef1234567818': 'Patricia Chang',
};

export function staffName(userId: string | null | undefined): string {
    if (!userId) return '--';
    return STAFF_NAMES[userId] ?? userId.slice(0, 8);
}
