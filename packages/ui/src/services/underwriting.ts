// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    RiskAssessmentSchema,
    ComplianceResultSchema,
    type RiskAssessment,
    type ComplianceResultData,
} from '@/schemas/underwriting';

export async function fetchRiskAssessment(applicationId: number): Promise<RiskAssessment> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/risk-assessment`);
    return RiskAssessmentSchema.parse(data);
}

export async function fetchComplianceResult(applicationId: number): Promise<ComplianceResultData> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/compliance-result`);
    return ComplianceResultSchema.parse(data);
}
