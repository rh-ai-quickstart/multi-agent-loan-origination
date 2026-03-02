{{/*
Expand the name of the chart.
*/}}
{{- define "summit-cap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "summit-cap.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "summit-cap.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "summit-cap.labels" -}}
helm.sh/chart: {{ include "summit-cap.chart" . }}
{{ include "summit-cap.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "summit-cap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "summit-cap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "summit-cap.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "summit-cap.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image name helper
*/}}
{{- define "summit-cap.image" -}}
{{- $registry := .Values.global.imageRegistry -}}
{{- $repository := .Values.global.imageRepository -}}
{{- $name := .name -}}
{{- $tag := .tag | default .Values.global.imageTag -}}
{{- printf "%s/%s/%s:%s" $registry $repository $name $tag -}}
{{- end }}

{{/*
API labels
*/}}
{{- define "summit-cap.api.labels" -}}
{{ include "summit-cap.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
API selector labels
*/}}
{{- define "summit-cap.api.selectorLabels" -}}
{{ include "summit-cap.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
UI labels
*/}}
{{- define "summit-cap.ui.labels" -}}
{{ include "summit-cap.labels" . }}
app.kubernetes.io/component: ui
{{- end }}

{{/*
UI selector labels
*/}}
{{- define "summit-cap.ui.selectorLabels" -}}
{{ include "summit-cap.selectorLabels" . }}
app.kubernetes.io/component: ui
{{- end }}

{{/*
Database labels
*/}}
{{- define "summit-cap.database.labels" -}}
{{ include "summit-cap.labels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "summit-cap.database.selectorLabels" -}}
{{ include "summit-cap.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Keycloak labels
*/}}
{{- define "summit-cap.keycloak.labels" -}}
{{ include "summit-cap.labels" . }}
app.kubernetes.io/component: keycloak
{{- end }}

{{/*
Keycloak selector labels
*/}}
{{- define "summit-cap.keycloak.selectorLabels" -}}
{{ include "summit-cap.selectorLabels" . }}
app.kubernetes.io/component: keycloak
{{- end }}

{{/*
MinIO labels
*/}}
{{- define "summit-cap.minio.labels" -}}
{{ include "summit-cap.labels" . }}
app.kubernetes.io/component: minio
{{- end }}

{{/*
MinIO selector labels
*/}}
{{- define "summit-cap.minio.selectorLabels" -}}
{{ include "summit-cap.selectorLabels" . }}
app.kubernetes.io/component: minio
{{- end }}

