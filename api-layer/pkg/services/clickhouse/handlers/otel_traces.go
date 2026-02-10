// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"strings"

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

	if result := h.DB.Where("SpanAttributes['session.id'] LIKE ?", "%"+sessionID).Find(&traces); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return traces, result.Error
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
	if err := h.DB.Where("SpanAttributes['session.id'] IN (?)", sessionIDs).Find(&allTraces).Error; err != nil {
		logger.Zap.Error("Error fetching traces for session IDs", logger.Error(err), logger.Strings("sessionIDs", sessionIDs))
		return result, []string{}, err
	}

	// Group traces by session ID in memory
	for _, trace := range allTraces {
		sessionIDStr, exists := trace.SpanAttributes["session.id"]
		if !exists {
			continue
		}

		// Try to match against the requested session IDs
		matched := false
		for _, requestedID := range sessionIDs {
			if sessionIDStr == requestedID || strings.HasSuffix(sessionIDStr, requestedID) {
				result[requestedID] = append(result[requestedID], trace)
				matched = true
				break
			}
		}
		if !matched {
			// Fallback: use the raw session ID from the span
			result[sessionIDStr] = append(result[sessionIDStr], trace)
		}
	}

	// Calculate not found session IDs
	var notFoundSessionIds []string
	for _, requestedSessionID := range sessionIDs {
		if _, found := result[requestedSessionID]; !found {
			notFoundSessionIds = append(notFoundSessionIds, requestedSessionID)
		}
	}

	return result, notFoundSessionIds, nil
}

func (h Handler) GetSpanBySessionIDAndSpanID(sessionID string, spanID string) (models.OtelTraces, error) {
	var span models.OtelTraces

	result := h.DB.
		Where("SpanAttributes['session.id'] LIKE ?", "%"+sessionID).
		Where("SpanId = ?", spanID).
		First(&span)

	if result.Error != nil {
		logger.Zap.Error("Error fetching span", logger.Error(result.Error))
		return span, result.Error
	}
	return span, nil
}
