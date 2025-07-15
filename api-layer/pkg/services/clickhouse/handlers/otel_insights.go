// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"github.com/cisco-eti/layer-api/pkg/logger"
	"github.com/cisco-eti/layer-api/pkg/services/clickhouse/models"
)

func (h Handler) GetMostFrequentlyUsedAgents() ([]models.AgentsUsage, error) {

	// Query most frequently used agents
	var results []models.AgentsUsage
	err := h.DB.Raw(`
		SELECT SpanName, COUNT(*) AS usage_count
		FROM otel_traces
		WHERE (ParentSpanId = '' OR ParentSpanId IS NULL)
		GROUP BY SpanName
		ORDER BY usage_count DESC
		LIMIT 10
	`).Scan(&results).Error
	if err != nil {
		logger.Zap.Error("Error", logger.Error(err))
		return nil, err
	}
	return results, nil
}

func (h Handler) GetTokenUsageCountPerAgent() ([]models.AgentsTokenUsage, error) {

	// Query most frequently used agents
	var results []models.AgentsTokenUsage
	err := h.DB.Raw(`
		SELECT
			ServiceName,
			SUM(toInt64OrZero(SpanAttributes['llm.usage.total_tokens'])) AS total_tokens
		FROM otel_traces
		WHERE SpanAttributes['llm.usage.total_tokens'] != ''
		GROUP BY ServiceName
		ORDER BY total_tokens DESC;
	`).Scan(&results).Error
	if err != nil {
		logger.Zap.Error("Error", logger.Error(err))
		return nil, err
	}
	return results, nil
}

func (h Handler) GetResponseLatencyStatsPerAgent() ([]models.ResponseLatencyPerAgent, error) {

	// Query most frequently used agents
	var results []models.ResponseLatencyPerAgent
	res := h.DB.Table("otel_metrics_histogram").
		Select(`ResourceAttributes['service.name'] AS ServiceName,
		COUNT(*) AS TotalRequests,
		SUM(Sum)/1000 AS TotalLatency,
		AVG(Sum)/1000 AS AvgLatency,
		MAX(Max)/1000 AS MaxLatency,
		MIN(Min)/1000 AS MinLatency`).
		Where("MetricName = ?", "response_latency").
		Group("ServiceName").
		Order("AvgLatency DESC").
		Find(&results)
	if res.Error != nil {
		logger.Zap.Error("Error", logger.Error(res.Error))
		return nil, res.Error
	}
	return results, nil
}

func (h Handler) GetCallGraph(executionId string) ([]models.CallGraph, error) {

	// Query call graph based on execution ID
	var results []models.CallGraph
	err := h.DB.Raw(`
    WITH
        ordered_spans AS (
            SELECT
                Timestamp,
                SpanName,
                JSONExtractString(SpanAttributes, 'execution.id') AS execution_id
            FROM otel_traces
            WHERE (execution_id IS NOT NULL) AND (ServiceName LIKE ?)
			AND (ParentSpanId = '' OR ParentSpanId IS NULL)
            ORDER BY Timestamp ASC
        ),
        span_list AS (
            SELECT
                groupArray(Timestamp) AS timestamps,
                groupArray(SpanName) AS spans
            FROM ordered_spans
        )
    SELECT
        if(index = 1, 'START', spans[index - 1]) AS previous_span,
        spans[index] AS current_span,
        if(index = length(spans), 'END', spans[index + 1]) AS next_span,
        timestamps[index] AS Timestamp
    FROM span_list
    ARRAY JOIN range(1, length(spans) + 1) AS index
    ORDER BY Timestamp ASC
`, "%"+executionId+"?").Scan(&results).Error
	if err != nil {
		logger.Zap.Error("Error", logger.Error(err))
		return nil, err
	}
	return results, nil
}

func (h Handler) GetAGPMetrics(executionId string) ([]models.AGPMetrics, error) {

	// Query call graph based on execution ID
	var results []models.AGPMetrics
	err := h.DB.Raw(`
    SELECT SpanName AS MetricName, SpanAttributes AS Attributes, Timestamp
	FROM otel_traces
    	WHERE ServiceName LIKE ?
    	AND SpanName IN ('connection_events', 'connection_latency', 'chain_completion_time', 'error_rates')
    ORDER BY Timestamp ASC
`, "%"+executionId+"%").Scan(&results).Error
	if err != nil {
		logger.Zap.Error("Error", logger.Error(err))
		return nil, err
	}
	return results, nil
}
