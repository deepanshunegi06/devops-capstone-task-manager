{{- define "taskmanager.labels" -}}
app.kubernetes.io/name: taskmanager
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "taskmanager.idleColor" -}}
{{- if eq .Values.activeColor "blue" -}}green{{- else -}}blue{{- end -}}
{{- end -}}
