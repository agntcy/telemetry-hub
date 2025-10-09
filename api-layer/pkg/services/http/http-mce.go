// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package http

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

// MCE Response structures for Swagger documentation

// MCEStatusResponse represents the response from GET /mce/status
type MCEStatusResponse struct {
	Status    string `json:"status" example:"ok"`
	Message   string `json:"message" example:"Metric Computation Engine is running"`
	Timestamp string `json:"timestamp" example:"2023-07-24T15:04:05.123456"`
	Service   string `json:"service" example:"metrics_computation_engine"`
}

// MCEMetricsResponse represents the response from GET /mce/metrics
type MCEMetricsResponse struct {
	TotalMetrics  int                  `json:"total_metrics" example:"9"`
	NativeMetrics int                  `json:"native_metrics" example:"7"`
	PluginMetrics int                  `json:"plugin_metrics" example:"2"`
	Metrics       MCEMetricsCollection `json:"metrics"`
}

// MCEMetricsCollection contains native and plugin metrics
type MCEMetricsCollection struct {
	Native  map[string]MCEMetricInfo `json:"native"`
	Plugins map[string]MCEMetricInfo `json:"plugins"`
}

// MCEMetricInfo represents detailed information about a specific metric
type MCEMetricInfo struct {
	Name               string   `json:"name" example:"AgentToToolInteractions"`
	Class              string   `json:"class" example:"AgentToToolInteractions"`
	Module             string   `json:"module" example:"metrics_computation_engine.metrics.session.agent_to_tool_interactions"`
	AggregationLevel   string   `json:"aggregation_level" example:"session"`
	Description        string   `json:"description" example:"Collects the Agent to Tool Interactions counts throughout a trace."`
	RequiredParameters []string `json:"required_parameters"`
	Source             string   `json:"source"`
}

// MCEComputeRequest represents the request body for POST /mce/metrics/compute
type MCEComputeRequest struct {
	Metrics        []string       `json:"metrics" example:"AgentToToolInteractions,GraphDeterminismScore"`
	LLMJudgeConfig LLMJudgeConfig `json:"llm_judge_config"`
	BatchConfig    BatchConfig    `json:"batch_config"`
}

// LLMJudgeConfig represents LLM configuration
type LLMJudgeConfig struct {
	LLMBaseModelURL string `json:"LLM_BASE_MODEL_URL" example:"https://api.openai.com/v1"`
	LLMModelName    string `json:"LLM_MODEL_NAME" example:"gpt-4"`
	OpenAIAPIKey    string `json:"OPENAI_API_KEY" example:"sk-..."`
	CustomAPIKey    string `json:"CUSTOM_API_KEY" example:""`
}

// BatchTimeRange represents time range configuration
type BatchTimeRange struct {
	Start string `json:"start" example:"2023-07-24T00:00:00Z"`
	End   string `json:"end" example:"2023-07-24T23:59:59Z"`
}

// BatchConfig represents batch processing configuration
type BatchConfig struct {
	TimeRange   *BatchTimeRange `json:"time_range,omitempty"`
	NumSessions *int            `json:"num_sessions,omitempty" example:"10"`
	AppName     *string         `json:"app_name,omitempty" example:"my_app"`
}

// MCEComputeResponse represents the response from POST /mce/metrics/compute
type MCEComputeResponse struct {
	Metrics []string               `json:"metrics" example:"AgentToToolInteractions,GraphDeterminismScore"`
	Results map[string]interface{} `json:"results"`
}

// MCEServer handles proxying requests to the Metrics Computation Engine
type MCEServer struct {
	Enabled bool
	Config  MCEConfig
	Client  *http.Client
}

// MCEConfig holds configuration for connecting to the MCE server
type MCEConfig struct {
	Host    string
	Port    int
	BaseURL string
	Timeout time.Duration
}

// NewMCEConfig creates a new MCE configuration with defaults from environment variables
func NewMCEConfig() MCEConfig {
	host := os.Getenv("MCE_HOST")
	if host == "" {
		host = "localhost"
	}

	port := 8000
	if portStr := os.Getenv("MCE_PORT"); portStr != "" {
		if p, err := strconv.Atoi(portStr); err == nil {
			port = p
		}
	}

	baseURL := os.Getenv("MCE_BASE_URL")
	// baseURL can be empty string by default

	timeout := 30 * time.Second
	if timeoutStr := os.Getenv("MCE_TIMEOUT"); timeoutStr != "" {
		if t, err := strconv.Atoi(timeoutStr); err == nil {
			timeout = time.Duration(t) * time.Second
		}
	}

	return MCEConfig{
		Host:    host,
		Port:    port,
		BaseURL: baseURL,
		Timeout: timeout,
	}
}

// NewMCEServer creates a new MCE server instance
func NewMCEServer(enabled bool, config MCEConfig) *MCEServer {
	return &MCEServer{
		Enabled: enabled,
		Config:  config,
		Client: &http.Client{
			Timeout: config.Timeout,
		},
	}
}

// handleJSONError returns a JSON error response with the specified status code and message
func (ms *MCEServer) handleJSONError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	errorResponse := ErrorResponse{
		Error:  true,
		Status: statusCode,
		Reason: message,
	}
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(errorResponse)
}

// buildMCEURL constructs the URL for MCE server requests
func (ms *MCEServer) buildMCEURL(endpoint string) string {
	baseURL := fmt.Sprintf("http://%s:%d", ms.Config.Host, ms.Config.Port)
	if ms.Config.BaseURL != "" {
		baseURL = fmt.Sprintf("%s/%s", baseURL, ms.Config.BaseURL)
	}
	return fmt.Sprintf("%s/%s", baseURL, endpoint)
}

// proxyRequest forwards a request to the MCE server and returns the response
func (ms *MCEServer) proxyRequest(w http.ResponseWriter, r *http.Request, endpoint string) {
	if !ms.Enabled {
		ms.handleJSONError(w, http.StatusNotFound, "MCE endpoints are disabled")
		return
	}

	// Build target URL
	targetURL := ms.buildMCEURL(endpoint)

	// Create new request
	var body io.Reader
	if r.Body != nil {
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			ms.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error reading request body: %v", err))
			return
		}
		body = bytes.NewReader(bodyBytes)
		r.Body.Close()
	}

	req, err := http.NewRequest(r.Method, targetURL, body)
	if err != nil {
		ms.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error creating request: %v", err))
		return
	}

	// Copy headers (excluding hop-by-hop headers)
	for name, values := range r.Header {
		// Skip hop-by-hop headers
		if name == "Connection" || name == "Keep-Alive" || name == "Proxy-Authenticate" ||
			name == "Proxy-Authorization" || name == "Te" || name == "Trailers" ||
			name == "Transfer-Encoding" || name == "Upgrade" {
			continue
		}
		for _, value := range values {
			req.Header.Add(name, value)
		}
	}

	// Forward query parameters
	req.URL.RawQuery = r.URL.RawQuery

	// Make the request
	resp, err := ms.Client.Do(req)
	if err != nil {
		ms.handleJSONError(w, http.StatusBadGateway, fmt.Sprintf("Error connecting to MCE server: %v", err))
		return
	}
	defer resp.Body.Close()

	// Read the response body first
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		ms.handleJSONError(w, http.StatusBadGateway, fmt.Sprintf("Error reading MCE server response: %v", err))
		return
	}

	// Check if the MCE server returned an error status code
	if resp.StatusCode >= 400 {
		// Convert MCE server error to our standardized JSON error format
		var mceError map[string]interface{}
		errorMessage := fmt.Sprintf("MCE server error (status %d)", resp.StatusCode)

		// Try to extract error details from MCE response
		if json.Unmarshal(responseBody, &mceError) == nil {
			if details, ok := mceError["details"].(string); ok && details != "" {
				errorMessage = fmt.Sprintf("MCE server error: %s", details)
			} else if message, ok := mceError["message"].(string); ok && message != "" {
				errorMessage = fmt.Sprintf("MCE server error: %s", message)
			} else if detail, ok := mceError["detail"].(string); ok && detail != "" {
				errorMessage = fmt.Sprintf("MCE server error: %s", detail)
			}
		}

		// Return standardized error response
		ms.handleJSONError(w, resp.StatusCode, errorMessage)
		return
	}

	// Copy response headers for successful responses
	for name, values := range resp.Header {
		for _, value := range values {
			w.Header().Add(name, value)
		}
	}

	// Set status code
	w.WriteHeader(resp.StatusCode)

	// Copy response body
	if _, err := io.Copy(w, bytes.NewReader(responseBody)); err != nil {
		// Log error but don't send another response as headers are already sent
		fmt.Printf("Error copying response body: %v\n", err)
	}
}

// @Summary      Get available metrics
// @Description  Get list of available metrics from MCE server
// @Tags         MCE
// @Accept       json
// @Produce      json
// @Success      200 {object} MCEMetricsResponse "List of available metrics"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "MCE endpoints disabled"
// @Failure      502 {object} ErrorResponse "MCE server unavailable"
// @Router       /mce/metrics [get]
func (ms *MCEServer) GetMetrics(w http.ResponseWriter, r *http.Request) {
	ms.proxyRequest(w, r, "metrics")
}

// @Summary      Get MCE server status
// @Description  Get status information from MCE server
// @Tags         MCE
// @Accept       json
// @Produce      json
// @Success      200 {object} MCEStatusResponse "Server status"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "MCE endpoints disabled"
// @Failure      502 {object} ErrorResponse "MCE server unavailable"
// @Router       /mce/status [get]
func (ms *MCEServer) GetStatus(w http.ResponseWriter, r *http.Request) {
	ms.proxyRequest(w, r, "status")
}

// @Summary      Compute metrics
// @Description  Compute metrics based on provided configuration
// @Tags         MCE
// @Accept       json
// @Produce      json
// @Param        config body MCEComputeRequest true "Metrics computation configuration"
// @Success      200 {object} MCEComputeResponse "Computed metrics results"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "MCE endpoints disabled"
// @Failure      502 {object} ErrorResponse "MCE server unavailable"
// @Router       /mce/metrics/compute [post]
func (ms *MCEServer) ComputeMetrics(w http.ResponseWriter, r *http.Request) {
	ms.proxyRequest(w, r, "compute_metrics")
}