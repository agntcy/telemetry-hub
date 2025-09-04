// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	"gorm.io/gorm"
)

func (h Handler) GetSessionIDS(startTime, endTime time.Time) ([]models.SessionID, error) {
	var traces []models.SessionID

	query := h.DB.Table("otel_traces").Select("splitByChar('_', SpanAttributes['session.id'])[2] as ID, SpanName, Timestamp, ScopeName, ServiceName")
	var result *gorm.DB
	result = query.Where("SpanName LIKE ?", "%graph%").Order("Timestamp DESC").
		Find(&traces)
	if result.Error != nil {
		return traces, result.Error
	}
	return traces, nil

}

func (h Handler) GetSessionIDSUnique(startTime, endTime time.Time) (sessionIDs []models.SessionUniqueID, err error) {

	query := h.DB.Table("otel_traces").Select("splitByChar('_', SpanAttributes['session.id'])[2] as ID, MIN(Timestamp) as StartTimestamp")
	var result *gorm.DB
	result = query.Where("Timestamp >= ? AND Timestamp <= ?", startTime, endTime).
		Where("SpanName LIKE ?", "%graph%").Where("SpanAttributes['session.id'] != ''").Order("StartTimestamp DESC").Group("splitByChar('_', SpanAttributes['session.id'])[2]").
		Find(&sessionIDs)

	if result.Error != nil {
		return sessionIDs, result.Error
	}
	return sessionIDs, nil

}

func (h Handler) GetTracesForSessionID(sessionID string) ([]string, error) {
	var traceIds []string

	query := h.DB.Table("otel_traces").Select("TraceId").Distinct()
	result := query.Where("splitByChar('_', SpanAttributes['session.id'])[2] = ?", sessionID).Order("Timestamp DESC").
		Find(&traceIds)

	if result.Error != nil {
		return traceIds, result.Error
	}
	return traceIds, nil
}

func (h Handler) GetSpansForTraceID(traceID string) ([]models.TraceId, error) {
	var spans []models.TraceId

	query := h.DB.Table("otel_traces").Select("TraceId as ID")
	result := query.Where("TraceId = ?", traceID).Order("Timestamp DESC").Find(&spans)

	if result.Error != nil {
		return spans, result.Error
	}
	return spans, nil
}
