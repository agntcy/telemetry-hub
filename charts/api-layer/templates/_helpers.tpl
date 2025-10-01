{{/*
Expand the name of the chart.
*/}}
{{- define "obs-api-layer.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "obs-api-layer.fullname" -}}
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
{{- define "obs-api-layer.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "obs-api-layer.labels" -}}
helm.sh/chart: {{ include "obs-api-layer.chart" . }}
{{ include "obs-api-layer.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "obs-api-layer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "obs-api-layer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "obs-api-layer.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "obs-api-layer.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the secret containing the obs-api server secrets
*/}}
{{- define "server.secretName" -}}
{{- $secretName := printf "%s-server-secret" (include "obs-api-layer.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.server.secret.name -}}
    {{- $secretName = .Values.server.secret.name -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}

{{/*
Return the secret containing the clickhouse secrets
*/}}
{{- define "clickhouse.secretName" -}}
{{- $secretName := printf "%s-clickhouse-secret" (include "obs-api-layer.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.clickhouseSettings.secret.name -}}
    {{- $secretName = .Values.clickhouseSettings.secret.name -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}


{{/*
Return the secret containing the tls certificate secrets
*/}}
{{- define "TLSCertificate.secretName" -}}
{{- $secretName := printf "%s-tls-secret" (include "obs-api-layer.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.TLSCertificate.secretName -}}
    {{- $secretName = .Values.TLSCertificate.secretName -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}
