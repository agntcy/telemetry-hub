// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
)

func (h Handler) AddMetric(metric models.Metric) (models.Metric, error) {
	if result := h.DB.Create(&metric); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return metric, result.Error
	}
	return metric, nil
}

func (h Handler) GetMetricsBySessionIdAndScope(sessionId string, scope string) (metrics []models.Metric, err error) {
	if result := h.DB.Where("SessionId = ?", sessionId).Where("Scope = ?", scope).Find(&metrics); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return nil, result.Error
	}
	return metrics, nil
}

func (h Handler) GetMetricsBySpanIdAndScope(spanId string, scope string) (metrics []models.Metric, err error) {
	if result := h.DB.Where("SpanId = ?", spanId).Where("Scope = ?", scope).Find(&metrics); result.Error != nil {
		logger.Zap.Error("Error", logger.Error(result.Error))
		return nil, result.Error
	}
	return metrics, nil
}
