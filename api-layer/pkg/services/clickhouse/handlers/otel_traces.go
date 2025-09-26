// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"strings"
	"time"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/common"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
)

func (h Handler) GetTraces() ([]models.OtelTraces, error) {
	var traces []models.OtelTraces
	if result := h.DB.Find(&traces).Limit(10); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return traces, result.Error
	}
	return traces, nil
}

func (h Handler) GetTracesBySessionID(sessionID string) ([]models.OtelTraces, error) {
	var traces []models.OtelTraces
	// Fix: change LIKE clause to EQUAL
	if result := h.DB.Where("splitByChar('_', SpanAttributes['session.id'])[2] = ? OR SpanAttributes['session.id'] = ?", sessionID, sessionID).Find(&traces); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return traces, result.Error
	}

	// Return 404 if no traces found for the session ID
	if len(traces) == 0 {
		return traces, models.NewNotFoundError("no traces found for session ID: " + sessionID)
	}

	return traces, nil
}

func (h Handler) GetTracesBySessionIDs(sessionIDs []string) (map[string][]models.OtelTraces, []string, error) {
	result := make(map[string][]models.OtelTraces)

	if len(sessionIDs) == 0 {
		return result, []string{}, nil
	}

	var allTraces []models.OtelTraces

	// Single query to get all traces for all session IDs
	if err := h.DB.Where("splitByChar('_', SpanAttributes['session.id'])[2] IN (?) OR  SpanAttributes['session.id'] IN (?)", sessionIDs, sessionIDs).Find(&allTraces).Error; err != nil {
		logger.Zap.Error("Error fetching traces for session IDs", logger.Error(err), logger.Strings("sessionIDs", sessionIDs))
		return result, []string{}, err
	}

	// Group traces by session ID in memory
	for _, trace := range allTraces {
		// Extract session ID from the span attributes
		sessionIDStr, exists := trace.SpanAttributes["session.id"]
		if !exists {
			continue
		}

		// Parse session ID using the same logic as the query
		// ClickHouse splitByChar('_', SpanAttributes['session.id'])[2] uses 1-based indexing
		// So [2] in ClickHouse = [1] in Go (0-based indexing)
		parts := strings.Split(sessionIDStr, "_")
		if len(parts) < 2 {
			continue
		}
		extractedSessionID := parts[1] // ClickHouse [2] = Go [1]

		// Add trace to the appropriate session group
		result[extractedSessionID] = append(result[extractedSessionID], trace)
	}

	// Calculate not found session IDs by comparing requested vs found
	var notFoundSessionIds []string
	for _, requestedSessionID := range sessionIDs {
		if _, found := result[requestedSessionID]; !found {
			notFoundSessionIds = append(notFoundSessionIds, requestedSessionID)
		}
	}

	return result, notFoundSessionIds, nil
}

func (h Handler) GetExecutionGraphBySessionID(sessionID string) (graph string, timestamp time.Time, err error) {
	var trace models.OtelTraces
	// Fix: change LIKE clause to EQUAL
	if result := h.DB.Where("SpanName LIKE '%.graph' AND splitByChar('_', SpanAttributes['session.id'])[2] = ? OR SpanAttributes['session.id'] = ?", sessionID, sessionID).Order("Timestamp DESC").First(&trace); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return graph, timestamp, result.Error
	}

	graph = trace.SpanAttributes[common.GRAPH_PARAM]
	if graph == "" {
		return graph, timestamp, models.NewNotFoundError("no graph found for session ID: " + sessionID)
	}

	timestamp = trace.Timestamp
	return graph, timestamp, nil

}

func (h Handler) GetTraceBySpanNameSessionIDAndAgent(spanName string, sessionID string, agentName string) (trace models.OtelTraces, err error) {
	if result := h.DB.Where("SpanName = ? AND (ServiceName = ? AND splitByChar('_', SpanAttributes['session.id'])[2] = ? OR SpanAttributes['session.id'] = ?)", spanName, agentName, sessionID, sessionID).First(&trace); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return trace, result.Error
	}
	return trace, nil
}
