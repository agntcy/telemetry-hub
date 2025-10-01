{{/*
Expand the name of the chart.
*/}}
{{- define "obs-mce.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "obs-mce.fullname" -}}
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
{{- define "obs-mce.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "obs-mce.labels" -}}
helm.sh/chart: {{ include "obs-mce.chart" . }}
{{ include "obs-mce.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "obs-mce.selectorLabels" -}}
app.kubernetes.io/name: {{ include "obs-mce.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "obs-mce.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "obs-mce.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the secret containing the obs-mce server secrets
*/}}
{{- define "server.secretName" -}}
{{- $secretName := printf "%s-server-secret" (include "obs-mce.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.server.secretName -}}
    {{- $secretName = .Values.server.secretName -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}

{{/*
Return the secret containing the api-layer secrets
*/}}
{{- define "api-layer.secretName" -}}
{{- $secretName := printf "%s-api-layer-secret" (include "obs-mce.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.apiLayer.secretName -}}
    {{- $secretName = .Values.apiLayer.secretName -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}


{{/*
Return the secret containing the tls certificate secrets
*/}}
{{- define "TLSCertificate.secretName" -}}
{{- $secretName := printf "%s-tls-secret" (include "obs-mce.name" .) | trunc 63 | trimSuffix "-" -}}
{{- if .Values.TLSCertificate.secretName -}}
    {{- $secretName = .Values.TLSCertificate.secretName -}}
{{- end -}}
{{- printf "%s" (tpl $secretName $) -}}
{{- end -}}
