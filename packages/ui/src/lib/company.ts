// This project was developed with assistance from AI tools.
const _rtc = (window as unknown as Record<string, unknown>).__RUNTIME_CONFIG__ as
    | { COMPANY_NAME?: string; AGENT_NAME?: string }
    | undefined;
export const COMPANY_NAME =
    _rtc?.COMPANY_NAME || import.meta.env.VITE_COMPANY_NAME || 'Acme FinTech Company';
export const AGENT_NAME: string | undefined =
    _rtc?.AGENT_NAME || import.meta.env.VITE_AGENT_NAME || undefined;
