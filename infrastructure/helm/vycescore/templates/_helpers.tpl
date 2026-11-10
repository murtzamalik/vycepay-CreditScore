{{/*
Expand the name of the chart.
*/}}
{{- define "vycescore.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vycescore.fullname" -}}
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
{{- define "vycescore.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vycescore.labels" -}}
helm.sh/chart: {{ include "vycescore.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: vycescore-platform
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "vycescore.serviceLabels" -}}
{{ include "vycescore.labels" . }}
app.kubernetes.io/name: {{ .serviceName }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: {{ .component | default .serviceName }}
{{- end }}

{{/*
Service-specific selector labels
*/}}
{{- define "vycescore.selectorLabels" -}}
app.kubernetes.io/name: {{ .serviceName }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account for a given service
*/}}
{{- define "vycescore.serviceAccountName" -}}
{{- if .sa.create }}
{{- default .serviceName .sa.name }}
{{- else }}
{{- default "default" .sa.name }}
{{- end }}
{{- end }}

{{/*
Image string helper
*/}}
{{- define "vycescore.image" -}}
{{- printf "%s:%s" .repository (.tag | default "latest") }}
{{- end }}
