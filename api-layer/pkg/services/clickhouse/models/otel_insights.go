// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package models

type AgentsUsage struct {
	SpanName   string `json:"agent_name"`
	UsageCount int    `json:"usage_count"`
}

type AgentsTokenUsage struct {
	ServiceName string `json:"agent_name"`
	TotalTokens int    `json:"total_tokens"`
}

type ResponseLatencyPerAgent struct {
	ServiceName   string  `json:"service_name"`
	TotalRequests int     `json:"total_requests"`
	TotalLatency  float64 `json:"total_latency"`
	AvgLatency    float64 `json:"avg_latency"`
	MaxLatency    float64 `json:"max_latency"`
	MinLatency    float64 `json:"min_latency"`
}

type CallGraph struct {
	AgentID      string `json:"agent_id"`
	ServiceName  string `json:"service_name"`
	PreviousSpan string `json:"previous_span"`
	CurrentSpan  string `json:"current_span"`
	NextSpan     string `json:"next_span"`
	Timestamp    string `json:"timestamp"`
}


type SessionID struct {
	ID          string `json:"id"`
	SpanName    string `json:"name"`
	Timestamp   string `json:"timestamp"`
	ScopeName   string `json:"scope_name"`
	ServiceName string `json:"service_name"`
}

type SessionUniqueID struct {
	ID             string `json:"id"`
	StartTimestamp string `json:"start_timestamp"`
}

type TraceId struct {
	ID string `json:"trace_id"`
}

type AGPMetrics struct {
	MetricName string            `json:"metric_name"`
	Attributes map[string]string `json:"span_attributes"`
	Timestamp  string            `json:"timestamp"`
}

// SessionsResponse represents the paginated response for /traces/sessions endpoint
type SessionsResponse struct {
	Data    []SessionUniqueID `json:"data"`
	HasNext bool              `json:"has_next"`
	HasPrev bool              `json:"has_prev"`
	Limit   int               `json:"limit"`
	Page    int               `json:"page"`
	Total   int               `json:"total"`
}

// SessionSpansResponse represents the response for /traces/session/spans endpoint
type SessionSpansResponse struct {
	Data               map[string][]OtelTraces `json:"data"`
	NotFoundSessionIds []string                `json:"notfound_session_ids"`
}