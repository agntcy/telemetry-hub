// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package services

import (
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
)

// DataService defines the interface for data operations
type DataService interface {
	GetSessionIDSUnique(startTime, endTime time.Time) ([]models.SessionUniqueID, error)
	AddMetric(metric models.Metric) (models.Metric, error)
	GetMetricsBySessionIdAndScope(sessionID string, scope string) ([]models.Metric, error)
	GetMetricsBySpanIdAndScope(spanID string, scope string) ([]models.Metric, error)
	GetTracesBySessionID(sessionID string) ([]models.OtelTraces, error)
}
