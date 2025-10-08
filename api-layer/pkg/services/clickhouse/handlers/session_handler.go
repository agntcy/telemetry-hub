// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
)

func (h Handler) GetSessionIDS(startTime, endTime time.Time) ([]models.SessionID, error) {
	var traces []models.SessionID

	result := h.DB.
		Table("otel_traces").
		Select("SpanAttributes['session.id'] AS ID, SpanName, Timestamp, ScopeName, ServiceName").
		Where("SpanAttributes['session.id'] != ''").
		Where("Timestamp >= ? AND Timestamp <= ?", startTime, endTime).
		Order("Timestamp DESC").
		Find(&traces)

	if result.Error != nil {
		return nil, result.Error
	}
	return traces, nil
}

func (h Handler) GetSessionIDSWithPrompts(startTime, endTime time.Time) ([]models.SessionUniqueID, error) {
    var sessionIDs []models.SessionUniqueID

    result := h.DB.
        Table("otel_traces").
        Select(`
            SpanAttributes['session.id'] AS ID,
            MIN(Timestamp) AS StartTimestamp,
            argMin(
                SpanAttributes['gen_ai.prompt.0.content'],
                Timestamp
            ) AS Prompt
        `).
        Where("SpanAttributes['session.id'] != ''").
        Where("SpanAttributes['gen_ai.prompt.0.role'] = 'user'").
        Group("SpanAttributes['session.id']").
        Having("MIN(Timestamp) >= ? AND MIN(Timestamp) <= ?", startTime, endTime).
        Order("StartTimestamp DESC").
        Find(&sessionIDs)

    if result.Error != nil {
        return nil, result.Error
    }
    return sessionIDs, nil
}

func (h Handler) GetSessionIDSWithPromptsWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) (sessionIDs []models.SessionUniqueID, total int, err error) {
    baseQuery := h.DB.
        Table("otel_traces").
        Select(`
            splitByChar('_', SpanAttributes['session.id'])[2] as ID,
            MIN(Timestamp) as StartTimestamp,
            argMin(
                SpanAttributes['gen_ai.prompt.0.content'],
                Timestamp
            ) AS Prompt
        `).
        Where("has(SpanAttributes, 'session.id') = 1").
        Where("SpanAttributes['session.id'] != ''").
        Where("SpanAttributes['gen_ai.prompt.0.role'] = 'user'").
        Where("Timestamp >= ? AND Timestamp <= ?", startTime, endTime)

    if nameFilter != nil && *nameFilter != "" {
        baseQuery = baseQuery.Where("SpanAttributes['session.id'] LIKE ?", *nameFilter+"%")
    }

    // Get total count
    var totalCount int64
    countQuery := baseQuery.Group("splitByChar('_', SpanAttributes['session.id'])[2]")
    if err := h.DB.Table("(?) as sub", countQuery).Count(&totalCount).Error; err != nil {
        return sessionIDs, 0, err
    }
    total = int(totalCount)

    // Get paginated results
    offset := page * limit
    result := baseQuery.
        Group("splitByChar('_', SpanAttributes['session.id'])[2]").
        Order("StartTimestamp DESC").
        Offset(offset).
        Limit(limit).
        Find(&sessionIDs)

    if result.Error != nil {
        return sessionIDs, total, result.Error
    }
    return sessionIDs, total, nil
}


func (h Handler) GetSessionIDSUnique(startTime, endTime time.Time) ([]models.SessionUniqueID, error) {
	var sessionIDs []models.SessionUniqueID

	result := h.DB.
		Table("otel_traces").
		Select("SpanAttributes['session.id'] AS ID, MIN(Timestamp) AS StartTimestamp").
		Where("SpanAttributes['session.id'] != ''").
		Group("SpanAttributes['session.id']").
		// Filter by the computed minimum per group (avoid alias in HAVING for portability)
		Having("MIN(Timestamp) >= ? AND MIN(Timestamp) <= ?", startTime, endTime).
		Order("StartTimestamp DESC").
		Find(&sessionIDs)

	if result.Error != nil {
		return nil, result.Error
	}
	return sessionIDs, nil
}

func (h Handler) GetSessionIDSUniqueWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) (sessionIDs []models.SessionUniqueID, total int, err error) {
	baseQuery := h.DB.
		Table("otel_traces").
		Select("splitByChar('_', SpanAttributes['session.id'])[2] as ID, MIN(Timestamp) as StartTimestamp").
		Where("has(SpanAttributes, 'session.id') = 1").
		Where("SpanAttributes['session.id'] != ''").
		Where("Timestamp >= ? AND Timestamp <= ?", startTime, endTime)

	if nameFilter != nil && *nameFilter != "" {
		baseQuery = baseQuery.Where("SpanAttributes['session.id'] LIKE ?", *nameFilter+"%")
	}

	// Get total count
	var totalCount int64
	countQuery := baseQuery.Group("splitByChar('_', SpanAttributes['session.id'])[2]")
	if err := h.DB.Table("(?) as sub", countQuery).Count(&totalCount).Error; err != nil {
		return sessionIDs, 0, err
	}
	total = int(totalCount)

	// Get paginated results
	offset := page * limit
	result := baseQuery.
		Group("splitByChar('_', SpanAttributes['session.id'])[2]").
		Order("StartTimestamp DESC").
		Offset(offset).
		Limit(limit).
		Find(&sessionIDs)

	if result.Error != nil {
		return sessionIDs, total, result.Error
	}
	return sessionIDs, total, nil
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
