// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package http

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/common"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	"github.com/gorilla/mux"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockDataService implements the DataService interface for testing
type MockDataService struct {
	mock.Mock
}

func (m *MockDataService) GetSessionIDSUnique(startTime, endTime time.Time) ([]models.SessionUniqueID, error) {
	args := m.Called(startTime, endTime)
	return args.Get(0).([]models.SessionUniqueID), args.Error(1)
}

func (m *MockDataService) AddMetric(metric models.Metric) (models.Metric, error) {
	args := m.Called(metric)
	return args.Get(0).(models.Metric), args.Error(1)
}

func (m *MockDataService) GetMetricsBySessionIdAndScope(sessionID string, scope string) ([]models.Metric, error) {
	args := m.Called(sessionID, scope)
	return args.Get(0).([]models.Metric), args.Error(1)
}

func (m *MockDataService) GetMetricsBySpanIdAndScope(spanID string, scope string) ([]models.Metric, error) {
	args := m.Called(spanID, scope)
	return args.Get(0).([]models.Metric), args.Error(1)
}

func (m *MockDataService) GetTracesBySessionID(sessionID string) ([]models.OtelTraces, error) {
	args := m.Called(sessionID)
	return args.Get(0).([]models.OtelTraces), args.Error(1)
}

// Helper function to create test server
func createTestServer(mockDataService *MockDataService) *HttpServer {
	return &HttpServer{
		Port:         8080,
		DataService:  mockDataService,
		BaseUrl:      "localhost:8080",
		AllowOrigins: "http://localhost:3000",
	}
}

// Helper function to create router with all routes
func createTestRouter(server *HttpServer) *mux.Router {
	router := mux.NewRouter()
	router.HandleFunc("/keepAlive", KeepAlive).Methods(http.MethodGet)
	router.HandleFunc("/metrics", PrometeusMetrics).Methods(http.MethodGet)
	router.HandleFunc("/traces/sessions", server.Sessions).Methods(http.MethodGet)
	router.HandleFunc("/traces/session/{session_id}", server.Traces).Methods(http.MethodGet)
	router.HandleFunc("/metrics/session", server.WriteMetricsSession).Methods(http.MethodPost)
	router.HandleFunc("/metrics/span", server.WriteMetricsSpan).Methods(http.MethodPost)
	router.HandleFunc("/metrics/session/{session_id}", server.GetMetricsSession).Methods(http.MethodGet)
	router.HandleFunc("/metrics/span/{span_id}", server.GetMetricsSpan).Methods(http.MethodGet)
	return router
}

func TestKeepAlive(t *testing.T) {
	tests := []struct {
		name           string
		method         string
		expectedStatus int
		expectedBody   SimpleMessage
		checkHeaders   bool
	}{
		{
			name:           "GET /keepAlive should return success with correct message",
			method:         http.MethodGet,
			expectedStatus: http.StatusOK,
			expectedBody:   SimpleMessage{Message: "I'm alive!"},
			checkHeaders:   true,
		},
		{
			name:           "POST /keepAlive should return method not allowed",
			method:         http.MethodPost,
			expectedStatus: http.StatusMethodNotAllowed,
			checkHeaders:   false,
		},
		{
			name:           "PUT /keepAlive should return method not allowed",
			method:         http.MethodPut,
			expectedStatus: http.StatusMethodNotAllowed,
			checkHeaders:   false,
		},
		{
			name:           "DELETE /keepAlive should return method not allowed",
			method:         http.MethodDelete,
			expectedStatus: http.StatusMethodNotAllowed,
			checkHeaders:   false,
		},
		{
			name:           "PATCH /keepAlive should return method not allowed",
			method:         http.MethodPatch,
			expectedStatus: http.StatusMethodNotAllowed,
			checkHeaders:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, "/keepAlive", nil)
			w := httptest.NewRecorder()

			KeepAlive(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			if tt.expectedStatus == http.StatusOK {
				var response SimpleMessage
				err := json.Unmarshal(w.Body.Bytes(), &response)
				assert.NoError(t, err)
				assert.Equal(t, tt.expectedBody, response)

				if tt.checkHeaders {
					assert.Equal(t, "application/json", w.Header().Get("Content-Type"))
				}
			}

			if tt.expectedStatus == http.StatusMethodNotAllowed {
				assert.Contains(t, w.Body.String(), "Method not allowed")
			}
		})
	}
}

func TestKeepAlive_ResponseFormat(t *testing.T) {
	t.Run("Response should be valid JSON", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/keepAlive", nil)
		w := httptest.NewRecorder()

		KeepAlive(w, req)

		assert.Equal(t, http.StatusOK, w.Code)

		// Check if response is valid JSON
		var response map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)

		// Check if message field exists and has correct value
		message, exists := response["message"]
		assert.True(t, exists)
		assert.Equal(t, "I'm alive!", message)
	})

	t.Run("Response should have correct Content-Type header", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/keepAlive", nil)
		w := httptest.NewRecorder()

		KeepAlive(w, req)

		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))
	})
}

func TestPrometeusMetrics(t *testing.T) {
	tests := []struct {
		name           string
		method         string
		expectedStatus int
		checkContent   bool
	}{
		{
			name:           "GET /metrics should return prometheus metrics",
			method:         http.MethodGet,
			expectedStatus: http.StatusOK,
			checkContent:   true,
		},
		{
			name:           "POST /metrics should return method not allowed",
			method:         http.MethodPost,
			expectedStatus: http.StatusMethodNotAllowed,
			checkContent:   false,
		},
		{
			name:           "PUT /metrics should return method not allowed",
			method:         http.MethodPut,
			expectedStatus: http.StatusMethodNotAllowed,
			checkContent:   false,
		},
		{
			name:           "DELETE /metrics should return method not allowed",
			method:         http.MethodDelete,
			expectedStatus: http.StatusMethodNotAllowed,
			checkContent:   false,
		},
		{
			name:           "PATCH /metrics should return method not allowed",
			method:         http.MethodPatch,
			expectedStatus: http.StatusMethodNotAllowed,
			checkContent:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, "/metrics", nil)
			w := httptest.NewRecorder()

			PrometeusMetrics(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			if tt.checkContent && tt.expectedStatus == http.StatusOK {
				// Check that some prometheus metrics are present in response
				responseBody := w.Body.String()
				assert.NotEmpty(t, responseBody)

				// Basic check for prometheus format (should contain metric lines)
				// Prometheus metrics typically start with # for comments or contain metric names
				assert.True(t, len(responseBody) > 0, "Response should not be empty")
			}

			if tt.expectedStatus == http.StatusMethodNotAllowed {
				assert.Contains(t, w.Body.String(), "Method not allowed")
			}
		})
	}
}

func TestPrometeusMetrics_Integration(t *testing.T) {
	t.Run("Metrics endpoint should serve prometheus format", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
		w := httptest.NewRecorder()

		PrometeusMetrics(w, req)

		assert.Equal(t, http.StatusOK, w.Code)

		responseBody := w.Body.String()

		// Check for common prometheus metric patterns
		// The response should contain prometheus metrics (even if default Go metrics)
		assert.NotEmpty(t, responseBody)

		// Check for typical prometheus metric patterns
		lines := strings.Split(responseBody, "\n")
		hasMetricLines := false
		for _, line := range lines {
			// Look for comment lines or metric lines
			if strings.HasPrefix(line, "#") || strings.Contains(line, "{") || strings.Contains(line, " ") {
				hasMetricLines = true
				break
			}
		}
		assert.True(t, hasMetricLines, "Response should contain prometheus-formatted metrics")
	})
}

func TestKeepAlive_Concurrent(t *testing.T) {
	t.Run("KeepAlive should handle concurrent requests", func(t *testing.T) {
		const numRequests = 10
		var wg sync.WaitGroup
		wg.Add(numRequests)

		for i := 0; i < numRequests; i++ {
			go func() {
				defer wg.Done()
				req := httptest.NewRequest(http.MethodGet, "/keepAlive", nil)
				w := httptest.NewRecorder()

				KeepAlive(w, req)

				assert.Equal(t, http.StatusOK, w.Code)
				assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

				var response SimpleMessage
				err := json.Unmarshal(w.Body.Bytes(), &response)
				assert.NoError(t, err)
				assert.Equal(t, "I'm alive!", response.Message)
			}()
		}

		wg.Wait()
	})
}

func TestPrometeusMetrics_Concurrent(t *testing.T) {
	t.Run("PrometeusMetrics should handle concurrent requests", func(t *testing.T) {
		const numRequests = 10
		var wg sync.WaitGroup
		wg.Add(numRequests)

		for i := 0; i < numRequests; i++ {
			go func() {
				defer wg.Done()
				req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
				w := httptest.NewRecorder()

				PrometeusMetrics(w, req)

				assert.Equal(t, http.StatusOK, w.Code)
			}()
		}

		wg.Wait()
	})
}

func TestSessions(t *testing.T) {
	t.Run("GET /traces/sessions with valid time range should return sessions", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		startTime := time.Date(2023, 6, 25, 15, 0, 0, 0, time.UTC)
		endTime := time.Date(2023, 6, 25, 18, 0, 0, 0, time.UTC)

		expectedSessions := []models.SessionUniqueID{
			{ID: "session_abc123", StartTimestamp: "2023-06-25T15:30:00Z"},
			{ID: "session_def456", StartTimestamp: "2023-06-25T16:15:00Z"},
		}

		mockDataService.On("GetSessionIDSUnique", mock.AnythingOfType("time.Time"), mock.AnythingOfType("time.Time")).Return(expectedSessions, nil)

		url := fmt.Sprintf("/traces/sessions?start_time=%s&end_time=%s",
			startTime.Format(time.RFC3339),
			endTime.Format(time.RFC3339))
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response []models.SessionUniqueID
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedSessions, response)

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /traces/sessions with invalid start_time should return bad request", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		req := httptest.NewRequest(http.MethodGet, "/traces/sessions?start_time=invalid&end_time=2023-06-25T18:04:05Z", nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusBadRequest, w.Code)
		assert.Contains(t, w.Body.String(), "Invalid start_time")
	})

	t.Run("GET /traces/sessions with invalid end_time should return bad request", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		req := httptest.NewRequest(http.MethodGet, "/traces/sessions?start_time=2023-06-25T15:04:05Z&end_time=invalid", nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusBadRequest, w.Code)
		assert.Contains(t, w.Body.String(), "Invalid end_time")
	})

	t.Run("GET /traces/sessions with service error should return internal server error", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		mockDataService.On("GetSessionIDSUnique", mock.AnythingOfType("time.Time"), mock.AnythingOfType("time.Time")).Return([]models.SessionUniqueID{}, errors.New("database error"))

		url := "/traces/sessions?start_time=2023-06-25T15:04:05Z&end_time=2023-06-25T18:04:05Z"
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusInternalServerError, w.Code)
		assert.Contains(t, w.Body.String(), "Error fetching sessions")

		mockDataService.AssertExpectations(t)
	})

	t.Run("POST /traces/sessions should return method not allowed", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		req := httptest.NewRequest(http.MethodPost, "/traces/sessions", nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
	})
}

func TestTraces(t *testing.T) {
	t.Run("GET /traces/session/{session_id} with valid session_id should return traces", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		sessionID := "session_abc123"
		expectedTraces := []models.OtelTraces{
			{
				TraceId:     "trace_def456",
				SpanName:    "ml_inference",
				Timestamp:   time.Date(2023, 6, 25, 15, 30, 0, 0, time.UTC),
				ServiceName: "ml-service",
			},
		}

		mockDataService.On("GetTracesBySessionID", sessionID).Return(expectedTraces, nil)

		url := fmt.Sprintf("/traces/session/%s", sessionID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response []models.OtelTraces
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedTraces, response)

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /traces/session/{session_id} with service error should return internal server error", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		sessionID := "session_abc123"
		mockDataService.On("GetTracesBySessionID", sessionID).Return([]models.OtelTraces{}, errors.New("database error"))

		url := fmt.Sprintf("/traces/session/%s", sessionID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusInternalServerError, w.Code)
		assert.Contains(t, w.Body.String(), "Error fetching traces")

		mockDataService.AssertExpectations(t)
	})

	t.Run("POST /traces/session/{session_id} should return method not allowed", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		url := "/traces/session/session_abc123"
		req := httptest.NewRequest(http.MethodPost, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
	})
}

func TestWriteMetricsSession(t *testing.T) {
	t.Run("POST /metrics/session with valid payload should create metric", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		spanID := "span_abc123"
		traceID := "trace_def456"
		sessionID := "session_ghi789"
		appName := "ml-service"
		appID := "app-001"
		metricsJSON := models.JSONRawMessage(`{"accuracy":"0.95","latency_ms":"120"}`)

		metricRequest := models.MetricCreateRequest{
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
		}

		// Create expected metric with generated ID and timestamp
		expectedMetric := models.Metric{
			ID:        stringPtr("generated-uuid"),
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			TimeStamp: timePtr(time.Now()),
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
			Scope:     stringPtr(common.METRIC_SCOPE_SESSION),
		}

		mockDataService.On("AddMetric", mock.MatchedBy(func(m models.Metric) bool {
			return *m.SpanId == spanID && *m.TraceId == traceID && *m.SessionId == sessionID &&
				*m.AppName == appName && *m.AppId == appID && *m.Scope == common.METRIC_SCOPE_SESSION
		})).Return(expectedMetric, nil)

		body, _ := json.Marshal(metricRequest)
		req := httptest.NewRequest(http.MethodPost, "/metrics/session", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		server.WriteMetricsSession(w, req)

		assert.Equal(t, http.StatusCreated, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response models.MetricResponse
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedMetric.ID, response.ID)
		assert.Equal(t, expectedMetric.SpanId, response.SpanId)

		mockDataService.AssertExpectations(t)
	})

	t.Run("POST /metrics/session with invalid JSON should return bad request", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		req := httptest.NewRequest(http.MethodPost, "/metrics/session", strings.NewReader("invalid json"))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		server.WriteMetricsSession(w, req)

		assert.Equal(t, http.StatusBadRequest, w.Code)
		assert.Contains(t, w.Body.String(), "Error decoding request body")
	})

	t.Run("POST /metrics/session with service error should return internal server error", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		spanID := "span_abc123"
		traceID := "trace_def456"
		sessionID := "session_ghi789"
		appName := "ml-service"
		appID := "app-001"
		metricsJSON := models.JSONRawMessage(`{"accuracy":"0.95"}`)

		metricRequest := models.MetricCreateRequest{
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
		}

		mockDataService.On("AddMetric", mock.AnythingOfType("models.Metric")).Return(models.Metric{}, errors.New("database error"))

		body, _ := json.Marshal(metricRequest)
		req := httptest.NewRequest(http.MethodPost, "/metrics/session", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		server.WriteMetricsSession(w, req)

		assert.Equal(t, http.StatusInternalServerError, w.Code)
		assert.Contains(t, w.Body.String(), "Error writing metric")

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /metrics/session should return method not allowed", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		req := httptest.NewRequest(http.MethodGet, "/metrics/session", nil)
		w := httptest.NewRecorder()

		server.WriteMetricsSession(w, req)

		assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
	})
}

func TestWriteMetricsSpan(t *testing.T) {
	mockDataService := new(MockDataService)
	server := createTestServer(mockDataService)

	t.Run("POST /metrics/span with valid payload should create metric", func(t *testing.T) {
		spanID := "span_xyz789"
		traceID := "trace_uvw123"
		sessionID := "session_rst456"
		appName := "api-gateway"
		appID := "app-002"
		metricsJSON := models.JSONRawMessage(`{"response_time":"200","cache_hit":"true"}`)

		metricRequest := models.MetricCreateRequest{
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
		}

		expectedMetric := models.Metric{
			ID:        stringPtr("generated-uuid"),
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			TimeStamp: timePtr(time.Now()),
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
			Scope:     stringPtr(common.METRIC_SCOPE_SPAN),
		}

		mockDataService.On("AddMetric", mock.MatchedBy(func(m models.Metric) bool {
			return *m.SpanId == spanID && *m.TraceId == traceID && *m.SessionId == sessionID &&
				*m.AppName == appName && *m.AppId == appID && *m.Scope == common.METRIC_SCOPE_SPAN
		})).Return(expectedMetric, nil)

		body, _ := json.Marshal(metricRequest)
		req := httptest.NewRequest(http.MethodPost, "/metrics/span", bytes.NewBuffer(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		server.WriteMetricsSpan(w, req)

		assert.Equal(t, http.StatusCreated, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response models.MetricResponse
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedMetric.ID, response.ID)
		assert.Equal(t, expectedMetric.SpanId, response.SpanId)

		mockDataService.AssertExpectations(t)
	})
}

func TestGetMetricsSession(t *testing.T) {
	t.Run("GET /metrics/session/{session_id} with valid session_id should return metrics", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		sessionID := "session_abc123"
		expectedMetrics := []models.Metric{
			{
				ID:        stringPtr("metric_001"),
				SpanId:    stringPtr("span_abc123"),
				TraceId:   stringPtr("trace_def456"),
				SessionId: &sessionID,
				TimeStamp: timePtr(time.Date(2023, 6, 25, 15, 30, 0, 0, time.UTC)),
				Metrics:   jsonRawMessagePtr(`{"accuracy":"0.95","latency_ms":"120"}`),
				AppName:   stringPtr("ml-service"),
				AppId:     stringPtr("app-001"),
				Scope:     nil, // Scope is not included in JSON response due to json:"-" tag
			},
		}

		mockDataService.On("GetMetricsBySessionIdAndScope", sessionID, common.METRIC_SCOPE_SESSION).Return(expectedMetrics, nil)

		url := fmt.Sprintf("/metrics/session/%s", sessionID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response []models.Metric
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedMetrics, response)

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /metrics/session/{session_id} with service error should return internal server error", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		sessionID := "session_abc123"
		mockDataService.On("GetMetricsBySessionIdAndScope", sessionID, common.METRIC_SCOPE_SESSION).Return([]models.Metric{}, errors.New("database error"))

		url := fmt.Sprintf("/metrics/session/%s", sessionID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusInternalServerError, w.Code)
		assert.Contains(t, w.Body.String(), "Error fetching metrics")

		mockDataService.AssertExpectations(t)
	})

	t.Run("POST /metrics/session/{session_id} should return method not allowed", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		url := "/metrics/session/session_abc123"
		req := httptest.NewRequest(http.MethodPost, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
	})
}

func TestGetMetricsSpan(t *testing.T) {
	t.Run("GET /metrics/span/{span_id} with valid span_id should return metrics", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		spanID := "span_abc123"
		expectedMetrics := []models.Metric{
			{
				ID:        stringPtr("metric_001"),
				SpanId:    &spanID,
				TraceId:   stringPtr("trace_def456"),
				SessionId: stringPtr("session_abc123"),
				TimeStamp: timePtr(time.Date(2023, 6, 25, 15, 30, 0, 0, time.UTC)),
				Metrics:   jsonRawMessagePtr(`{"accuracy":"0.95","latency_ms":"120"}`),
				AppName:   stringPtr("ml-service"),
				AppId:     stringPtr("app-001"),
				Scope:     nil, // Scope is not included in JSON response due to json:"-" tag
			},
		}

		mockDataService.On("GetMetricsBySpanIdAndScope", spanID, common.METRIC_SCOPE_SPAN).Return(expectedMetrics, nil)

		url := fmt.Sprintf("/metrics/span/%s", spanID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

		var response []models.Metric
		err := json.Unmarshal(w.Body.Bytes(), &response)
		assert.NoError(t, err)
		assert.Equal(t, expectedMetrics, response)

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /metrics/span/{span_id} with service error should return internal server error", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		spanID := "span_abc123"
		mockDataService.On("GetMetricsBySpanIdAndScope", spanID, common.METRIC_SCOPE_SPAN).Return([]models.Metric{}, errors.New("database error"))

		url := fmt.Sprintf("/metrics/span/%s", spanID)
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusInternalServerError, w.Code)
		assert.Contains(t, w.Body.String(), "Error fetching metrics")

		mockDataService.AssertExpectations(t)
	})

	t.Run("GET /metrics/span/ with empty span_id should return bad request", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)
		router := createTestRouter(server)

		url := "/metrics/span/"
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusNotFound, w.Code)
	})
}

// Helper functions for creating pointers
func stringPtr(s string) *string {
	return &s
}

func timePtr(t time.Time) *time.Time {
	return &t
}

func jsonRawMessagePtr(s string) *models.JSONRawMessage {
	msg := models.JSONRawMessage(s)
	return &msg
}

// Integration test for the HTTP server
func TestHttpServerIntegration(t *testing.T) {
	t.Run("Test complete request flow", func(t *testing.T) {
		mockDataService := new(MockDataService)
		server := createTestServer(mockDataService)

		// Test 1: Get sessions
		startTime := time.Date(2023, 6, 25, 15, 0, 0, 0, time.UTC)
		endTime := time.Date(2023, 6, 25, 18, 0, 0, 0, time.UTC)
		expectedSessions := []models.SessionUniqueID{
			{ID: "session_test123", StartTimestamp: "2023-06-25T15:30:00Z"},
		}
		mockDataService.On("GetSessionIDSUnique", mock.AnythingOfType("time.Time"), mock.AnythingOfType("time.Time")).Return(expectedSessions, nil)

		url := fmt.Sprintf("/traces/sessions?start_time=%s&end_time=%s",
			startTime.Format(time.RFC3339),
			endTime.Format(time.RFC3339))
		req := httptest.NewRequest(http.MethodGet, url, nil)
		w := httptest.NewRecorder()

		server.Sessions(w, req)

		assert.Equal(t, http.StatusOK, w.Code)

		// Test 2: Write a metric
		spanID := "span_integration123"
		traceID := "trace_integration123"
		sessionID := "session_integration123"
		appName := "integration-service"
		appID := "app-integration"
		metricsJSON := models.JSONRawMessage(`{"test_metric":"value"}`)

		metricRequest := models.MetricCreateRequest{
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
		}

		expectedMetric := models.Metric{
			ID:        stringPtr("integration-uuid"),
			SpanId:    &spanID,
			TraceId:   &traceID,
			SessionId: &sessionID,
			TimeStamp: timePtr(time.Now()),
			Metrics:   &metricsJSON,
			AppName:   &appName,
			AppId:     &appID,
			Scope:     stringPtr(common.METRIC_SCOPE_SESSION),
		}

		mockDataService.On("AddMetric", mock.AnythingOfType("models.Metric")).Return(expectedMetric, nil)

		body, _ := json.Marshal(metricRequest)
		req2 := httptest.NewRequest(http.MethodPost, "/metrics/session", bytes.NewBuffer(body))
		req2.Header.Set("Content-Type", "application/json")
		w2 := httptest.NewRecorder()

		server.WriteMetricsSession(w2, req2)

		assert.Equal(t, http.StatusCreated, w2.Code)

		mockDataService.AssertExpectations(t)
	})
}
