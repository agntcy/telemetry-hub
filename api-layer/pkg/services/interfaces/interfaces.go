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
    GetSessionIDSWithPrompts(startTime, endTime time.Time) ([]models.SessionUniqueID, error)
	GetTracesBySessionID(sessionID string) ([]models.OtelTraces, error)
	GetTracesBySessionIDs(sessionIDs []string) (map[string][]models.OtelTraces, []string, error)
	GetSessionIDSUniqueWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) ([]models.SessionUniqueID, int, error)
	GetSessionIDSWithPromptsWithPagination(startTime, endTime time.Time, page, limit int, nameFilter *string) ([]models.SessionUniqueID, int, error)
	GetExecutionGraphBySessionID(sessionID string) (string, time.Time, error)
	GetTraceBySpanNameSessionIDAndAgent(spanName string, sessionID string, agentName string) (models.OtelTraces, error)
	GetCallGraph(sessionID string) ([]models.CallGraph, error)
}

// MetricsService defines the interface for metrics operations
type MetricsService interface {
	AddMetric(metric models.Metric) (models.Metric, error)
	GetMetricsBySessionIdAndScope(sessionID string, scope string) ([]models.Metric, error)
	GetMetricsBySpanIdAndScope(spanID string, scope string) ([]models.Metric, error)
}

// AnnotationService defines the interface for annotation operations
type AnnotationService interface {
	// Annotation Types
	CreateAnnotationType(annotationType *models.AnnotationType) (*models.AnnotationType, error)
	GetAnnotationTypes(page, limit int, groupID *string) ([]models.AnnotationType, int, error)
	GetAnnotationTypeByID(id string) (*models.AnnotationType, error)
	UpdateAnnotationType(id string, updates *models.AnnotationTypeUpdate) (*models.AnnotationType, error)
	DeleteAnnotationType(id string) error

	// Annotations
	CreateAnnotation(annotation *models.Annotation) (*models.Annotation, error)
	GetAnnotations(page, limit int, groupID, sessionID, reviewerID *string) ([]models.Annotation, int, error)
	GetAnnotationByID(id string) (*models.Annotation, error)
	UpdateAnnotation(id string, updates *models.AnnotationUpdate) (*models.Annotation, error)
	DeleteAnnotation(id string) error

	// Annotation Groups
	CreateAnnotationGroup(group *models.AnnotationGroup) (*models.AnnotationGroup, error)
	GetAnnotationGroups(page, limit int, name *string) ([]models.AnnotationGroup, int, error)
	GetAnnotationGroupByID(id string) (*models.AnnotationGroup, error)
	UpdateAnnotationGroup(id string, updates *models.AnnotationGroupUpdate) (*models.AnnotationGroup, error)
	DeleteAnnotationGroup(id string) error

	// Annotation Group Items
	CreateAnnotationGroupItems(groupID string, sessionIDs []string) ([]models.AnnotationGroupItem, error)
	GetAnnotationGroupItems(groupID string, page, limit int) ([]models.AnnotationGroupItem, int, error)
	DeleteAnnotationGroupItem(groupID, itemID string) error

	// Consensus
	ComputeConsensus(groupID string, method string) (*models.AnnotationConsensus, error)
	GetConsensusReports(groupID string, page, limit int) ([]models.AnnotationConsensus, int, error)
	GetConsensusReport(groupID, consensusID string) (*models.AnnotationConsensus, error)
	DeleteConsensusReport(groupID, consensusID string) error

	// Annotation Datasets
	CreateAnnotationDataset(dataset *models.AnnotationDataset) (*models.AnnotationDataset, error)
	GetAnnotationDatasets(page, limit int, tags, name *string) ([]models.AnnotationDataset, int, error)
	GetAnnotationDatasetByID(id string) (*models.AnnotationDataset, error)
	DeleteAnnotationDataset(id string) error
	GetAnnotationDatasetItemCount(datasetID string) (int, error)

	// Annotation Dataset Items
	ImportAnnotationDatasetItems(datasetID string, items []models.AnnotationDatasetItemCreate) ([]string, map[int]string, error)
	GetAnnotationDatasetItems(datasetID string, itemIDs []string) (map[string]models.AnnotationDatasetItem, []string, error)
}
