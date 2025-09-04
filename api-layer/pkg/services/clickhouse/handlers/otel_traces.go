// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package handlers

import (
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
