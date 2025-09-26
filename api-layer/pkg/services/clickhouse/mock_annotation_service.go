// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package clickhouse

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	services "github.com/agntcy/telemetry-hub/api-layer/pkg/services/interfaces"
)

// MockAnnotationService provides a mock implementation of AnnotationService for testing
type MockAnnotationService struct {
	annotationTypes []models.AnnotationType
	annotations     []models.Annotation
	groups          []models.AnnotationGroup
	groupItems      []models.AnnotationGroupItem
	consensus       []models.AnnotationConsensus
}

// NewMockAnnotationService creates a new mock annotation service
func NewMockAnnotationService() services.AnnotationService {
	mockGroups := []models.AnnotationGroup{
		{
			ID:           "test-group-id",
			Name:         "Test Group",
			Comment:      stringPtr("Mock test group for consensus testing"),
			MinReviews:   2,
			MaxReviews:   5,
			MaxReport:    5,
			Discontinued: false,
		},
	}

	return &MockAnnotationService{
		annotationTypes: []models.AnnotationType{},
		annotations:     []models.Annotation{},
		groups:          mockGroups,
		groupItems:      []models.AnnotationGroupItem{},
		consensus:       []models.AnnotationConsensus{},
	}
}

// Helper function for string pointers
func stringPtr(s string) *string {
	return &s
}

// Annotation Types
func (m *MockAnnotationService) CreateAnnotationType(annotationType *models.AnnotationType) (*models.AnnotationType, error) {
	annotationType.ID = fmt.Sprintf("type_%d", len(m.annotationTypes)+1)
	annotationType.CreationDate = time.Now()
	annotationType.UpdateDate = time.Now()
	m.annotationTypes = append(m.annotationTypes, *annotationType)
	return annotationType, nil
}

func (m *MockAnnotationService) GetAnnotationTypes(page, limit int, groupID *string) ([]models.AnnotationType, int, error) {
	start := (page - 1) * limit
	end := start + limit
	if start >= len(m.annotationTypes) {
		return []models.AnnotationType{}, len(m.annotationTypes), nil
	}
	if end > len(m.annotationTypes) {
		end = len(m.annotationTypes)
	}
	return m.annotationTypes[start:end], len(m.annotationTypes), nil
}

func (m *MockAnnotationService) GetAnnotationTypeByID(id string) (*models.AnnotationType, error) {
	for _, t := range m.annotationTypes {
		if t.ID == id {
			return &t, nil
		}
	}
	return nil, models.NewNotFoundError("annotation type not found")
}

func (m *MockAnnotationService) UpdateAnnotationType(id string, updates *models.AnnotationTypeUpdate) (*models.AnnotationType, error) {
	// Mock implementation
	return nil, models.NewNotFoundError("annotation type not found")
}

func (m *MockAnnotationService) DeleteAnnotationType(id string) error {
	for i, t := range m.annotationTypes {
		if t.ID == id {
			m.annotationTypes = append(m.annotationTypes[:i], m.annotationTypes[i+1:]...)
			return nil
		}
	}
	return models.NewNotFoundError("annotation type not found")
}

// Annotations
func (m *MockAnnotationService) CreateAnnotation(annotation *models.Annotation) (*models.Annotation, error) {
	annotation.ID = fmt.Sprintf("annotation_%d", len(m.annotations)+1)
	annotation.CreationDate = time.Now()
	annotation.UpdateDate = time.Now()
	m.annotations = append(m.annotations, *annotation)
	return annotation, nil
}

func (m *MockAnnotationService) GetAnnotations(page, limit int, groupID, sessionID, reviewerID *string) ([]models.Annotation, int, error) {
	filtered := []models.Annotation{}
	for _, a := range m.annotations {
		if sessionID != nil && a.SessionID != *sessionID {
			continue
		}
		if reviewerID != nil && a.ReviewerID != *reviewerID {
			continue
		}
		filtered = append(filtered, a)
	}

	start := (page - 1) * limit
	end := start + limit
	if start >= len(filtered) {
		return []models.Annotation{}, len(filtered), nil
	}
	if end > len(filtered) {
		end = len(filtered)
	}
	return filtered[start:end], len(filtered), nil
}

func (m *MockAnnotationService) GetAnnotationByID(id string) (*models.Annotation, error) {
	for _, a := range m.annotations {
		if a.ID == id {
			return &a, nil
		}
	}
	return nil, models.NewNotFoundError("annotation not found")
}

func (m *MockAnnotationService) UpdateAnnotation(id string, updates *models.AnnotationUpdate) (*models.Annotation, error) {
	for i, a := range m.annotations {
		if a.ID == id {
			if updates.AnnotationValue != "" {
				m.annotations[i].AnnotationValue = updates.AnnotationValue
			}
			if updates.Comment != nil {
				m.annotations[i].Comment = updates.Comment
			}
			if updates.Acceptance != nil {
				m.annotations[i].Acceptance = updates.Acceptance
			}
			if updates.AcceptanceID != nil {
				m.annotations[i].AcceptanceID = updates.AcceptanceID
			}
			m.annotations[i].UpdateDate = time.Now()
			return &m.annotations[i], nil
		}
	}
	return nil, models.NewNotFoundError("annotation not found")
}

func (m *MockAnnotationService) DeleteAnnotation(id string) error {
	for i, a := range m.annotations {
		if a.ID == id {
			m.annotations = append(m.annotations[:i], m.annotations[i+1:]...)
			return nil
		}
	}
	return models.NewNotFoundError("annotation not found")
}

// Annotation Groups
func (m *MockAnnotationService) CreateAnnotationGroup(group *models.AnnotationGroup) (*models.AnnotationGroup, error) {
	group.ID = fmt.Sprintf("group_%d", len(m.groups)+1)
	m.groups = append(m.groups, *group)
	return group, nil
}

func (m *MockAnnotationService) GetAnnotationGroups(page, limit int, name *string) ([]models.AnnotationGroup, int, error) {
	filtered := m.groups

	// Apply name filter if provided
	if name != nil {
		filtered = []models.AnnotationGroup{}
		for _, g := range m.groups {
			if g.Name == *name {
				filtered = append(filtered, g)
			}
		}
	}

	start := (page - 1) * limit
	end := start + limit
	if start >= len(filtered) {
		return []models.AnnotationGroup{}, len(filtered), nil
	}
	if end > len(filtered) {
		end = len(filtered)
	}
	return filtered[start:end], len(filtered), nil
}

func (m *MockAnnotationService) GetAnnotationGroupByID(id string) (*models.AnnotationGroup, error) {
	for _, g := range m.groups {
		if g.ID == id {
			return &g, nil
		}
	}
	return nil, models.NewNotFoundError("annotation group not found")
}

func (m *MockAnnotationService) UpdateAnnotationGroup(id string, updates *models.AnnotationGroupUpdate) (*models.AnnotationGroup, error) {
	for i, g := range m.groups {
		if g.ID == id {
			if updates.Name != nil {
				m.groups[i].Name = *updates.Name
			}
			if updates.Comment != nil {
				m.groups[i].Comment = updates.Comment
			}
			if updates.Discontinued != nil {
				m.groups[i].Discontinued = *updates.Discontinued
			}
			if updates.MinReviews != nil {
				m.groups[i].MinReviews = *updates.MinReviews
			}
			if updates.MaxReviews != nil {
				m.groups[i].MaxReviews = *updates.MaxReviews
			}
			if updates.MaxReport != nil && *updates.MaxReport > 0 {
				m.groups[i].MaxReport = *updates.MaxReport
			}
			return &m.groups[i], nil
		}
	}
	return nil, models.NewNotFoundError("annotation group not found")
}

func (m *MockAnnotationService) DeleteAnnotationGroup(id string) error {
	for i, g := range m.groups {
		if g.ID == id {
			m.groups = append(m.groups[:i], m.groups[i+1:]...)
			return nil
		}
	}
	return models.NewNotFoundError("annotation group not found")
}

// Annotation Group Items
func (m *MockAnnotationService) CreateAnnotationGroupItems(groupID string, sessionIDs []string) ([]models.AnnotationGroupItem, error) {
	items := []models.AnnotationGroupItem{}
	for _, sessionID := range sessionIDs {
		item := models.AnnotationGroupItem{
			ID:        fmt.Sprintf("item_%d", len(m.groupItems)+1),
			GroupID:   groupID,
			SessionID: sessionID,
		}
		m.groupItems = append(m.groupItems, item)
		items = append(items, item)
	}
	return items, nil
}

func (m *MockAnnotationService) GetAnnotationGroupItems(groupID string, page, limit int) ([]models.AnnotationGroupItem, int, error) {
	filtered := []models.AnnotationGroupItem{}
	for _, item := range m.groupItems {
		if item.GroupID == groupID {
			filtered = append(filtered, item)
		}
	}

	start := (page - 1) * limit
	end := start + limit
	if start >= len(filtered) {
		return []models.AnnotationGroupItem{}, len(filtered), nil
	}
	if end > len(filtered) {
		end = len(filtered)
	}
	return filtered[start:end], len(filtered), nil
}

func (m *MockAnnotationService) DeleteAnnotationGroupItem(groupID, itemID string) error {
	for i, item := range m.groupItems {
		if item.ID == itemID && item.GroupID == groupID {
			m.groupItems = append(m.groupItems[:i], m.groupItems[i+1:]...)
			return nil
		}
	}
	return models.NewNotFoundError("annotation group item not found")
}

// Consensus
func (m *MockAnnotationService) ComputeConsensus(groupID string, method string) (*models.AnnotationConsensus, error) {
	// Validate method parameter
	if method == "" {
		method = "majority"
	}
	if method != "majority" {
		return nil, models.NewValidationError("unsupported consensus method '" + method + "'. Only 'majority' is currently supported")
	}

	// Helper function to convert data to JSONRawMessage
	convertToJSONRaw := func(data interface{}) *models.JSONRawMessage {
		jsonBytes, _ := json.Marshal(data)
		raw := models.JSONRawMessage(jsonBytes)
		return &raw
	}

	consensus := &models.AnnotationConsensus{
		ID:                       fmt.Sprintf("consensus_%d", len(m.consensus)+1),
		GroupID:                  groupID,
		Method:                   method,
		Valid:                    true,
		QualityScore:             0.85,
		AnnotationStatistics:     convertToJSONRaw(map[string]interface{}{"reviewer1": map[string]interface{}{"agreements": 8, "total_annotations": 10, "agreement_rate": 80.0}}),
		AnnotationTypeStatistics: convertToJSONRaw([]interface{}{map[string]interface{}{"annotation_type_id": "type1", "annotation_type_name": "Quality Score", "annotation_type_type": "boolean", "observation_type": "session", "sessions_count": 5, "consensus": 4, "no_consensus": 1, "quality_score": 80.0, "consensus_rate": 80.0}}),
		ConsensusValues:          convertToJSONRaw([]interface{}{map[string]interface{}{"session_id": "session1", "observation_id": "obs1", "value": true}}),
		NoConsensusValues:        convertToJSONRaw([]interface{}{map[string]interface{}{"session_id": "session2", "observation_id": "obs2", "values": []interface{}{true, false}}}),
		ReviewersQualityScore:    convertToJSONRaw(map[string]interface{}{"reviewer1": 0.9, "reviewer2": 0.8}),
		ReviewersStats:           convertToJSONRaw(map[string]interface{}{"total_reviews": 10}),
		CreationDate:             time.Now(),
	}
	m.consensus = append(m.consensus, *consensus)
	return consensus, nil
}

func (m *MockAnnotationService) GetConsensusReports(groupID string, page, limit int) ([]models.AnnotationConsensus, int, error) {
	filtered := []models.AnnotationConsensus{}
	for _, c := range m.consensus {
		if c.GroupID == groupID {
			filtered = append(filtered, c)
		}
	}

	start := (page - 1) * limit
	end := start + limit
	if start >= len(filtered) {
		return []models.AnnotationConsensus{}, len(filtered), nil
	}
	if end > len(filtered) {
		end = len(filtered)
	}
	return filtered[start:end], len(filtered), nil
}

func (m *MockAnnotationService) GetConsensusReport(groupID, consensusID string) (*models.AnnotationConsensus, error) {
	for _, c := range m.consensus {
		if c.ID == consensusID && c.GroupID == groupID {
			return &c, nil
		}
	}
	return nil, models.NewNotFoundError("consensus report not found")
}

func (m *MockAnnotationService) DeleteConsensusReport(groupID, consensusID string) error {
	for i, c := range m.consensus {
		if c.ID == consensusID && c.GroupID == groupID {
			m.consensus = append(m.consensus[:i], m.consensus[i+1:]...)
			return nil
		}
	}
	return models.NewNotFoundError("consensus report not found")
}

// Dataset methods (mock implementations)

func (m *MockAnnotationService) CreateAnnotationDataset(dataset *models.AnnotationDataset) (*models.AnnotationDataset, error) {
	dataset.ID = "mock-dataset-id"
	dataset.CreationDate = time.Now()
	return dataset, nil
}

func (m *MockAnnotationService) GetAnnotationDatasets(page, limit int, tags, name *string) ([]models.AnnotationDataset, int, error) {
	mockDataset := models.AnnotationDataset{
		ID:           "mock-dataset-id",
		Name:         "Mock Dataset",
		Tags:         []string{"mock", "test"},
		CreationDate: time.Now(),
	}
	return []models.AnnotationDataset{mockDataset}, 1, nil
}

func (m *MockAnnotationService) GetAnnotationDatasetByID(id string) (*models.AnnotationDataset, error) {
	if id == "mock-dataset-id" {
		return &models.AnnotationDataset{
			ID:           "mock-dataset-id",
			Name:         "Mock Dataset",
			Tags:         []string{"mock", "test"},
			CreationDate: time.Now(),
		}, nil
	}
	return nil, models.NewNotFoundError("dataset not found")
}

func (m *MockAnnotationService) DeleteAnnotationDataset(id string) error {
	if id == "mock-dataset-id" {
		return nil
	}
	return models.NewNotFoundError("dataset not found")
}

func (m *MockAnnotationService) GetAnnotationDatasetItemCount(datasetID string) (int, error) {
	if datasetID == "mock-dataset-id" {
		return 5, nil
	}
	return 0, models.NewNotFoundError("dataset not found")
}

func (m *MockAnnotationService) ImportAnnotationDatasetItems(datasetID string, items []models.AnnotationDatasetItemCreate) ([]string, map[int]string, error) {
	if datasetID != "mock-dataset-id" {
		return nil, nil, models.NewNotFoundError("dataset not found")
	}

	successfulItems := make([]string, len(items))
	for i := range items {
		successfulItems[i] = fmt.Sprintf("mock-item-id-%d", i)
	}

	return successfulItems, map[int]string{}, nil
}

func (m *MockAnnotationService) GetAnnotationDatasetItems(datasetID string, itemIDs []string) (map[string]models.AnnotationDatasetItem, []string, error) {
	if datasetID != "mock-dataset-id" {
		return nil, nil, models.NewNotFoundError("dataset not found")
	}

	data := make(map[string]models.AnnotationDatasetItem)
	if len(itemIDs) == 0 {
		// Return all items
		data["mock-item-1"] = models.AnnotationDatasetItem{
			ID:             "mock-item-1",
			DatasetID:      datasetID,
			SessionID:      "mock-session-1",
			Input:          "Mock input",
			Output:         "Mock output",
			ExpectedOutput: "Mock expected output",
			Tags:           []string{"mock"},
			CreationDate:   time.Now(),
		}
	} else {
		// Return requested items
		for _, id := range itemIDs {
			if id == "mock-item-1" {
				data[id] = models.AnnotationDatasetItem{
					ID:             id,
					DatasetID:      datasetID,
					SessionID:      "mock-session-1",
					Input:          "Mock input",
					Output:         "Mock output",
					ExpectedOutput: "Mock expected output",
					Tags:           []string{"mock"},
					CreationDate:   time.Now(),
				}
			}
		}
	}

	return data, []string{}, nil
}
