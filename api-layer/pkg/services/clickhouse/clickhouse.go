// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package clickhouse

import (
	"net/url"
	"strconv"
	"time"

	"gorm.io/driver/clickhouse"
	"gorm.io/gorm"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/handlers"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
)

type ClickhouseService struct {
	Url          string
	User         string
	Pass         string
	Port         int
	DB           string
	clickhouseDB *gorm.DB
	Handlers     handlers.Handler
}

func (cs *ClickhouseService) Init() error {
	//connecto to the right db

	var err error
	dsn := "clickhouse://" + cs.User + ":" + url.QueryEscape(cs.Pass) + "@" + cs.Url + ":" + strconv.Itoa(cs.Port) + "/" + cs.DB + "?dial_timeout=10s&read_timeout=20s&allow_experimental_json_type=1"
	cs.clickhouseDB, err = gorm.Open(clickhouse.Open(dsn), &gorm.Config{})

	if err != nil {
		logger.Zap.Error("Failed to connect to database", logger.Error(err))
		return err
	}

	cs.clickhouseDB.AutoMigrate(&models.Metric{})
	cs.Handlers = handlers.New(cs.clickhouseDB)
	return nil
}

// GetSessionIDSUnique implements the DataService interface
func (cs *ClickhouseService) GetSessionIDSUnique(startTime, endTime time.Time) ([]models.SessionUniqueID, error) {
	return cs.Handlers.GetSessionIDSUnique(startTime, endTime)
}

// GetSessionIDSWithPrompts implements the DataService interface
func (cs *ClickhouseService) GetSessionIDSWithPrompts(startTime, endTime time.Time) ([]models.SessionUniqueID, error) {
    return cs.Handlers.GetSessionIDSWithPrompts(startTime, endTime)
}

// GetSessionIDSWithPromptsWithPagination implements the DataService interface
func (cs *ClickhouseService) GetSessionIDSWithPromptsWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) ([]models.SessionUniqueID, int, error) {
	return cs.Handlers.GetSessionIDSWithPromptsWithPagination(startTime, endTime, page, limit, nameFilter)
}

// GetSessionIDSUniqueWithPagination implements the DataService interface
func (cs *ClickhouseService) GetSessionIDSUniqueWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) ([]models.SessionUniqueID, int, error) {
	return cs.Handlers.GetSessionIDSUniqueWithPagination(startTime, endTime, page, limit, nameFilter)
}

// AddMetric implements the DataService interface
func (cs *ClickhouseService) AddMetric(metric models.Metric) (models.Metric, error) {
	return cs.Handlers.AddMetric(metric)
}

// GetMetricsBySessionIDAndScope implements the DataService interface
func (cs *ClickhouseService) GetMetricsBySessionIdAndScope(sessionID string, scope string) ([]models.Metric, error) {
	return cs.Handlers.GetMetricsBySessionIdAndScope(sessionID, scope)
}

// GetMetricsBySpanIdAndScope implements the DataService interface
func (cs *ClickhouseService) GetMetricsBySpanIdAndScope(spanID string, scope string) ([]models.Metric, error) {
	return cs.Handlers.GetMetricsBySpanIdAndScope(spanID, scope)
}

// GetTracesBySessionID implements the DataService interface
func (cs *ClickhouseService) GetTracesBySessionID(sessionID string) ([]models.OtelTraces, error) {
	return cs.Handlers.GetTracesBySessionID(sessionID)
}

// GetExecutionGraphBySessionID implements the DataService interface
func (cs *ClickhouseService) GetExecutionGraphBySessionID(sessionID string) (string, time.Time, error) {
	return cs.Handlers.GetExecutionGraphBySessionID(sessionID)
}

func (cs *ClickhouseService) GetCallGraph(sessionID string) ([]models.CallGraph, error) {
	return cs.Handlers.GetCallGraph(sessionID)
}

// GetTraceBySpanNameSessionIDAndAgent implements the DataService interface
func (cs *ClickhouseService) GetTraceBySpanNameSessionIDAndAgent(spanName string, sessionID string, agentName string) (models.OtelTraces, error) {
	return cs.Handlers.GetTraceBySpanNameSessionIDAndAgent(spanName, sessionID, agentName)
}


// GetTracesBySessionIDs implements the DataService interface
func (cs *ClickhouseService) GetTracesBySessionIDs(sessionIDs []string) (map[string][]models.OtelTraces, []string, error) {
	return cs.Handlers.GetTracesBySessionIDs(sessionIDs)
}
