// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package clickhouse

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"gorm.io/driver/clickhouse"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	services "github.com/agntcy/telemetry-hub/api-layer/pkg/services/interfaces"
)

// ClickhouseAnnotationService implements the AnnotationService interface using ClickHouse
type ClickhouseAnnotationService struct {
	Url          string
	User         string
	Pass         string
	Port         int
	DB           string
	clickhouseDB *gorm.DB
}

// NewClickhouseAnnotationService creates a new ClickHouse annotation service
func NewClickhouseAnnotationService(url, user, pass, db string, port int) (services.AnnotationService, error) {
	service := &ClickhouseAnnotationService{
		Url:  url,
		User: user,
		Pass: pass,
		Port: port,
		DB:   db,
	}

	// Initialize the connection
	if err := service.Init(); err != nil {
		logger.Zap.Error("Failed to initialize ClickHouse annotation service", logger.Error(err))
		return nil, err
	}

	return service, nil
}

// Init initializes the ClickHouse connection
func (cas *ClickhouseAnnotationService) Init() error {
	var err error
	dsn := "clickhouse://" + cas.User + ":" + url.QueryEscape(cas.Pass) + "@" + cas.Url + ":" + strconv.Itoa(cas.Port) + "/" + cas.DB + "?dial_timeout=10s&read_timeout=20s&allow_experimental_json_type=1"

	// Custom GORM logger to suppress "record not found" logs during validation checks
	// These are expected behaviors when checking for uniqueness constraints and foreign keys
	customLogger := gormlogger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags),
		gormlogger.Config{
			SlowThreshold:             time.Second,
			LogLevel:                  gormlogger.Error, // Only log actual errors
			IgnoreRecordNotFoundError: true,             // Don't log ErrRecordNotFound (expected during validations)
			Colorful:                  false,
		},
	)

	cas.clickhouseDB, err = gorm.Open(clickhouse.Open(dsn), &gorm.Config{
		Logger: customLogger,
	})

	if err != nil {
		logger.Zap.Error("Failed to connect to ClickHouse annotation database", logger.Error(err))
		return err
	}

	// Auto-migrate annotation tables - Note: ClickHouse doesn't support traditional migrations
	// We assume tables are already created via the SQL scripts
	logger.Zap.Info("ClickHouse annotation service initialized successfully")
	return nil
}

// Annotation Types

func (cas *ClickhouseAnnotationService) CreateAnnotationType(annotationType *models.AnnotationType) (*models.AnnotationType, error) {
	// Check if name already exists (enforce unique constraint at application level)
	var existingType models.AnnotationType
	err := cas.clickhouseDB.Where("name = ?", annotationType.Name).First(&existingType).Error
	if err == nil {
		// Name already exists
		return nil, models.NewConflictError("annotation type with this name already exists")
	}
	if err != gorm.ErrRecordNotFound {
		// Database error occurred
		logger.Zap.Error("Failed to check annotation type name uniqueness", logger.Error(err))
		return nil, err
	}

	// Insert the record
	result := cas.clickhouseDB.Create(annotationType)
	if result.Error != nil {
		logger.Zap.Error("Failed to create annotation type", logger.Error(result.Error))
		return nil, result.Error
	}

	// Since ClickHouse generates UUID and timestamps, we need to query back the inserted record
	// We'll use the name as a unique identifier to find the record we just inserted
	var insertedAnnotationType models.AnnotationType
	err = cas.clickhouseDB.Where("name = ?", annotationType.Name).
		Order("creation_date DESC").
		First(&insertedAnnotationType).Error

	if err != nil {
		logger.Zap.Error("Failed to retrieve created annotation type", logger.Error(err))
		return nil, err
	}

	return &insertedAnnotationType, nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationTypes(page, limit int, groupID *string) ([]models.AnnotationType, int, error) {
	var annotationTypes []models.AnnotationType
	var total int64

	query := cas.clickhouseDB.Model(&models.AnnotationType{})

	// If groupID is provided, filter by annotation types used in that group
	if groupID != nil {
		query = query.Where("id IN (SELECT DISTINCT unnest(annotation_type_ids) FROM annotation_groups WHERE id = ?)", *groupID)
	}

	// Get total count
	if err := query.Count(&total).Error; err != nil {
		logger.Zap.Error("Failed to count annotation types", logger.Error(err))
		return nil, 0, err
	}

	// Get paginated results
	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Find(&annotationTypes).Error; err != nil {
		logger.Zap.Error("Failed to get annotation types", logger.Error(err))
		return nil, 0, err
	}

	return annotationTypes, int(total), nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationTypeByID(id string) (*models.AnnotationType, error) {
	var annotationType models.AnnotationType

	result := cas.clickhouseDB.Where("id = ?", id).First(&annotationType)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation type not found")
		}
		logger.Zap.Error("Failed to get annotation type", logger.Error(result.Error))
		return nil, models.NewInternalError("failed to get annotation type", result.Error)
	}

	return &annotationType, nil
}

func (cas *ClickhouseAnnotationService) UpdateAnnotationType(id string, updates *models.AnnotationTypeUpdate) (*models.AnnotationType, error) {
	var annotationType models.AnnotationType

	// First, get the existing record
	if err := cas.clickhouseDB.Where("id = ?", id).First(&annotationType).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation type not found")
		}
		return nil, models.NewInternalError("failed to get annotation type", err)
	}

	// Apply updates - build list of fields to update
	updateFields := []string{}

	if updates.Name != nil {
		annotationType.Name = *updates.Name
		updateFields = append(updateFields, "name")
	}
	if updates.Comment != nil {
		annotationType.Comment = updates.Comment
		updateFields = append(updateFields, "comment")
	}
	if updates.Discontinued != nil {
		annotationType.Discontinued = *updates.Discontinued
		updateFields = append(updateFields, "discontinued")
	}

	// Only update if there are fields to update
	if len(updateFields) > 0 {
		result := cas.clickhouseDB.Model(&annotationType).Select(updateFields).Updates(&annotationType)
		if result.Error != nil {
			logger.Zap.Error("Failed to update annotation type", logger.Error(result.Error))
			return nil, models.NewInternalError("failed to update annotation type", result.Error)
		}
	}

	// Get the updated record
	if err := cas.clickhouseDB.Where("id = ?", id).First(&annotationType).Error; err != nil {
		return nil, models.NewInternalError("failed to get updated annotation type", err)
	}

	return &annotationType, nil
}

func (cas *ClickhouseAnnotationService) DeleteAnnotationType(id string) error {
	// Check if annotation type exists first
	var existingType models.AnnotationType
	err := cas.clickhouseDB.Where("id = ?", id).First(&existingType).Error
	if err == gorm.ErrRecordNotFound {
		return models.NewNotFoundError("annotation type not found")
	}
	if err != nil {
		logger.Zap.Error("Failed to check annotation type existence", logger.Error(err))
		return models.NewInternalError("failed to check annotation type existence", err)
	}

	// Check if any annotations are using this annotation type
	var annotationCount int64
	err = cas.clickhouseDB.Model(&models.Annotation{}).Where("annotation_type_id = ?", id).Count(&annotationCount).Error
	if err != nil {
		logger.Zap.Error("Failed to check annotation references", logger.Error(err))
		return models.NewInternalError("failed to check annotation references", err)
	}
	if annotationCount > 0 {
		return models.NewConflictError(fmt.Sprintf("cannot delete annotation type: %d annotations are still using this type", annotationCount))
	}

	// Check if any annotation groups are using this annotation type
	var groups []models.AnnotationGroup
	err = cas.clickhouseDB.Find(&groups).Error
	if err != nil {
		logger.Zap.Error("Failed to check annotation group references", logger.Error(err))
		return models.NewInternalError("failed to check annotation group references", err)
	}

	var referencingGroups []string
	for _, group := range groups {
		for _, typeID := range group.AnnotationTypeIDs {
			if typeID == id {
				referencingGroups = append(referencingGroups, group.Name)
				break
			}
		}
	}

	if len(referencingGroups) > 0 {
		return models.NewConflictError(fmt.Sprintf("cannot delete annotation type: annotation groups [%s] are still using this type", strings.Join(referencingGroups, ", ")))
	}

	// Safe to delete
	result := cas.clickhouseDB.Where("id = ?", id).Delete(&models.AnnotationType{})
	if result.Error != nil {
		logger.Zap.Error("Failed to delete annotation type", logger.Error(result.Error))
		return models.NewInternalError("failed to delete annotation type", result.Error)
	}

	return nil
}

// Annotations

func (cas *ClickhouseAnnotationService) CreateAnnotation(annotation *models.Annotation) (*models.Annotation, error) {
	// Validate foreign key constraint: annotation_type_id must exist
	var existingType models.AnnotationType
	err := cas.clickhouseDB.Where("id = ?", annotation.AnnotationTypeID).First(&existingType).Error
	if err == gorm.ErrRecordNotFound {
		return nil, models.NewValidationError("annotation type with ID '" + annotation.AnnotationTypeID + "' does not exist")
	}
	if err != nil {
		logger.Zap.Error("Failed to validate annotation type ID", logger.String("typeID", annotation.AnnotationTypeID), logger.Error(err))
		return nil, err
	}

	// Check if annotation type is discontinued
	if existingType.Discontinued {
		return nil, models.NewConflictError("annotation type with ID '" + annotation.AnnotationTypeID + "' is discontinued and cannot be used")
	}

	// If annotation has a group item, check if the associated group is discontinued
	if annotation.GroupItemID != "" {
		var existingGroupItem models.AnnotationGroupItem
		err = cas.clickhouseDB.Where("id = ?", annotation.GroupItemID).First(&existingGroupItem).Error
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewValidationError("annotation group item with ID '" + annotation.GroupItemID + "' does not exist")
		}
		if err != nil {
			logger.Zap.Error("Failed to validate annotation group item ID", logger.String("groupItemID", annotation.GroupItemID), logger.Error(err))
			return nil, err
		}

		var existingGroup models.AnnotationGroup
		err = cas.clickhouseDB.Where("id = ?", existingGroupItem.GroupID).First(&existingGroup).Error
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewValidationError("annotation group with ID '" + existingGroupItem.GroupID + "' does not exist")
		}
		if err != nil {
			logger.Zap.Error("Failed to validate annotation group ID", logger.String("groupID", existingGroupItem.GroupID), logger.Error(err))
			return nil, err
		}

		if existingGroup.Discontinued {
			return nil, models.NewConflictError("annotation group with ID '" + existingGroupItem.GroupID + "' is discontinued and cannot accept new annotations")
		}
	}

	// Check if (reviewer_id, observation_id, observation_type, annotation_type_id) combination already exists
	var existingAnnotation models.Annotation
	err = cas.clickhouseDB.Where("reviewer_id = ? AND observation_id = ? AND observation_type = ? AND annotation_type_id = ?",
		annotation.ReviewerID, annotation.ObservationID, annotation.ObservationType, annotation.AnnotationTypeID).
		First(&existingAnnotation).Error

	if err == nil {
		// Combination already exists
		return nil, models.NewConflictError("annotation with this reviewer, observation, observation type, and annotation type already exists")
	}
	if err != gorm.ErrRecordNotFound {
		// Database error occurred
		logger.Zap.Error("Failed to check annotation uniqueness", logger.Error(err))
		return nil, err
	}

	// Insert the record
	result := cas.clickhouseDB.Create(annotation)
	if result.Error != nil {
		logger.Zap.Error("Failed to create annotation", logger.Error(result.Error))
		return nil, result.Error
	}

	// Since ClickHouse generates UUID and timestamps, we need to query back the inserted record
	// We'll use multiple fields to uniquely identify the record we just inserted
	var insertedAnnotation models.Annotation
	err = cas.clickhouseDB.Where("annotation_type_id = ? AND reviewer_id = ? AND observation_id = ? AND observation_type = ?",
		annotation.AnnotationTypeID, annotation.ReviewerID, annotation.ObservationID, annotation.ObservationType).
		Order("creation_date DESC").
		First(&insertedAnnotation).Error

	if err != nil {
		logger.Zap.Error("Failed to retrieve created annotation", logger.Error(err))
		return nil, err
	}

	return &insertedAnnotation, nil
}

func (cas *ClickhouseAnnotationService) GetAnnotations(page, limit int, groupID, sessionID, reviewerID *string) ([]models.Annotation, int, error) {
	var annotations []models.Annotation
	var total int64

	query := cas.clickhouseDB.Model(&models.Annotation{})

	// Apply filters
	if sessionID != nil {
		query = query.Where("session_id = ?", *sessionID)
	}
	if reviewerID != nil {
		query = query.Where("reviewer_id = ?", *reviewerID)
	}
	if groupID != nil {
		// Filter by annotations that belong to items in the specified group
		query = query.Where("observation_id IN (SELECT session_id FROM annotation_group_items WHERE group_id = ?)", *groupID)
	}

	// Get total count
	if err := query.Count(&total).Error; err != nil {
		logger.Zap.Error("Failed to count annotations", logger.Error(err))
		return nil, 0, err
	}

	// Get paginated results
	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Find(&annotations).Error; err != nil {
		logger.Zap.Error("Failed to get annotations", logger.Error(err))
		return nil, 0, err
	}

	return annotations, int(total), nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationByID(id string) (*models.Annotation, error) {
	var annotation models.Annotation

	result := cas.clickhouseDB.Where("id = ?", id).First(&annotation)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation not found")
		}
		logger.Zap.Error("Failed to get annotation", logger.Error(result.Error))
		return nil, models.NewInternalError("failed to get annotation", result.Error)
	}

	return &annotation, nil
}

func (cas *ClickhouseAnnotationService) UpdateAnnotation(id string, updates *models.AnnotationUpdate) (*models.Annotation, error) {
	var annotation models.Annotation

	// First, get the existing record
	if err := cas.clickhouseDB.Where("id = ?", id).First(&annotation).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation not found")
		}
		return nil, models.NewInternalError("failed to get annotation", err)
	}

	// Apply updates
	if updates.AnnotationValue != "" {
		annotation.AnnotationValue = updates.AnnotationValue
	}
	if updates.Comment != nil {
		annotation.Comment = updates.Comment
	}
	if updates.Acceptance != nil {
		annotation.Acceptance = updates.Acceptance
	}
	if updates.AcceptanceID != nil {
		annotation.AcceptanceID = updates.AcceptanceID
	}

	result := cas.clickhouseDB.Save(&annotation)
	if result.Error != nil {
		logger.Zap.Error("Failed to update annotation", logger.Error(result.Error))
		return nil, models.NewInternalError("failed to update annotation", result.Error)
	}

	return &annotation, nil
}

func (cas *ClickhouseAnnotationService) DeleteAnnotation(id string) error {
	result := cas.clickhouseDB.Where("id = ?", id).Delete(&models.Annotation{})
	if result.Error != nil {
		logger.Zap.Error("Failed to delete annotation", logger.Error(result.Error))
		return models.NewInternalError("failed to delete annotation", result.Error)
	}

	if result.RowsAffected == 0 {
		return models.NewNotFoundError("annotation not found")
	}

	return nil
}

// Annotation Groups

func (cas *ClickhouseAnnotationService) CreateAnnotationGroup(group *models.AnnotationGroup) (*models.AnnotationGroup, error) {
	// Check if name already exists (enforce unique constraint at application level)
	var existingGroup models.AnnotationGroup
	err := cas.clickhouseDB.Where("name = ?", group.Name).First(&existingGroup).Error
	if err == nil {
		// Name already exists
		return nil, models.NewConflictError("annotation group with this name already exists")
	}
	if err != gorm.ErrRecordNotFound {
		// Database error occurred
		logger.Zap.Error("Failed to check annotation group name uniqueness", logger.Error(err))
		return nil, err
	}

	// Validate foreign key constraints: all annotation_type_ids must exist and not be discontinued
	for _, typeID := range group.AnnotationTypeIDs {
		if typeID == "" {
			continue // Skip empty IDs
		}
		var existingType models.AnnotationType
		err := cas.clickhouseDB.Where("id = ?", typeID).First(&existingType).Error
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewValidationError("annotation type with ID '" + typeID + "' does not exist")
		}
		if err != nil {
			logger.Zap.Error("Failed to validate annotation type ID", logger.String("typeID", typeID), logger.Error(err))
			return nil, err
		}

		// Check if annotation type is discontinued
		if existingType.Discontinued {
			return nil, models.NewConflictError("annotation type with ID '" + typeID + "' is discontinued and cannot be used in new annotation groups")
		}
	}

	// Insert the record
	result := cas.clickhouseDB.Create(group)
	if result.Error != nil {
		logger.Zap.Error("Failed to create annotation group", logger.Error(result.Error))
		return nil, result.Error
	}

	// Since ClickHouse generates UUID, we need to query back the inserted record
	// We'll use the name as a unique identifier to find the record we just inserted
	var insertedGroup models.AnnotationGroup
	err = cas.clickhouseDB.Where("name = ?", group.Name).
		Order("id DESC").
		First(&insertedGroup).Error

	if err != nil {
		logger.Zap.Error("Failed to retrieve created annotation group", logger.Error(err))
		return nil, err
	}

	return &insertedGroup, nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationGroups(page, limit int, name *string) ([]models.AnnotationGroup, int, error) {
	var groups []models.AnnotationGroup
	var total int64

	query := cas.clickhouseDB.Model(&models.AnnotationGroup{})

	// Apply name filter if provided
	if name != nil {
		query = query.Where("name = ?", *name)
	}

	// Get total count
	if err := query.Count(&total).Error; err != nil {
		logger.Zap.Error("Failed to count annotation groups", logger.Error(err))
		return nil, 0, err
	}

	// Get paginated results
	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Find(&groups).Error; err != nil {
		logger.Zap.Error("Failed to get annotation groups", logger.Error(err))
		return nil, 0, err
	}

	return groups, int(total), nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationGroupByID(id string) (*models.AnnotationGroup, error) {
	var group models.AnnotationGroup

	result := cas.clickhouseDB.Where("id = ?", id).First(&group)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation group not found")
		}
		logger.Zap.Error("Failed to get annotation group", logger.Error(result.Error))
		return nil, models.NewInternalError("failed to get annotation group", result.Error)
	}

	return &group, nil
}

func (cas *ClickhouseAnnotationService) UpdateAnnotationGroup(id string, updates *models.AnnotationGroupUpdate) (*models.AnnotationGroup, error) {
	var group models.AnnotationGroup

	// First, get the existing record
	if err := cas.clickhouseDB.Where("id = ?", id).First(&group).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("annotation group not found")
		}
		return nil, models.NewInternalError("failed to get annotation group", err)
	}

	// Apply updates - build list of fields to update
	updateFields := []string{}

	if updates.Name != nil {
		group.Name = *updates.Name
		updateFields = append(updateFields, "name")
	}
	if updates.Comment != nil {
		group.Comment = updates.Comment
		updateFields = append(updateFields, "comment")
	}
	if updates.Discontinued != nil {
		group.Discontinued = *updates.Discontinued
		updateFields = append(updateFields, "discontinued")
	}
	if updates.MinReviews != nil {
		group.MinReviews = *updates.MinReviews
		updateFields = append(updateFields, "min_reviews")
	}
	if updates.MaxReviews != nil {
		group.MaxReviews = *updates.MaxReviews
		updateFields = append(updateFields, "max_reviews")
	}
	if updates.MaxReport != nil && *updates.MaxReport > 0 {
		group.MaxReport = *updates.MaxReport
		updateFields = append(updateFields, "max_report")
	}

	// Only update if there are fields to update
	if len(updateFields) > 0 {
		result := cas.clickhouseDB.Model(&group).Select(updateFields).Updates(&group)
		if result.Error != nil {
			logger.Zap.Error("Failed to update annotation group", logger.Error(result.Error))
			return nil, models.NewInternalError("failed to update annotation group", result.Error)
		}
	}

	// Get the updated record
	if err := cas.clickhouseDB.Where("id = ?", id).First(&group).Error; err != nil {
		return nil, models.NewInternalError("failed to get updated annotation group", err)
	}

	return &group, nil
}

func (cas *ClickhouseAnnotationService) DeleteAnnotationGroup(id string) error {
	// Check if annotation group exists first
	var existingGroup models.AnnotationGroup
	err := cas.clickhouseDB.Where("id = ?", id).First(&existingGroup).Error
	if err == gorm.ErrRecordNotFound {
		return models.NewNotFoundError("annotation group not found")
	}
	if err != nil {
		logger.Zap.Error("Failed to check annotation group existence", logger.Error(err))
		return models.NewInternalError("failed to check annotation group existence", err)
	}

	// Check if any consensus reports are linked to this group
	var consensusCount int64
	err = cas.clickhouseDB.Model(&models.AnnotationConsensus{}).Where("group_id = ?", id).Count(&consensusCount).Error
	if err != nil {
		logger.Zap.Error("Failed to check consensus report references", logger.Error(err))
		return models.NewInternalError("failed to check consensus report references", err)
	}
	if consensusCount > 0 {
		return models.NewConflictError(fmt.Sprintf("cannot delete annotation group: %d consensus reports are still linked to this group", consensusCount))
	}

	// Check if any annotation group items reference this group
	var groupItemCount int64
	err = cas.clickhouseDB.Model(&models.AnnotationGroupItem{}).Where("group_id = ?", id).Count(&groupItemCount).Error
	if err != nil {
		logger.Zap.Error("Failed to check annotation group item references", logger.Error(err))
		return models.NewInternalError("failed to check annotation group item references", err)
	}
	if groupItemCount > 0 {
		return models.NewConflictError(fmt.Sprintf("cannot delete annotation group: %d annotation group items are still referencing this group", groupItemCount))
	}

	// Safe to delete
	result := cas.clickhouseDB.Where("id = ?", id).Delete(&models.AnnotationGroup{})
	if result.Error != nil {
		logger.Zap.Error("Failed to delete annotation group", logger.Error(result.Error))
		return models.NewInternalError("failed to delete annotation group", result.Error)
	}

	return nil
}

// Annotation Group Items

func (cas *ClickhouseAnnotationService) CreateAnnotationGroupItems(groupID string, sessionIDs []string) ([]models.AnnotationGroupItem, error) {
	// Validate foreign key constraint: group_id must exist
	var existingGroup models.AnnotationGroup
	err := cas.clickhouseDB.Where("id = ?", groupID).First(&existingGroup).Error
	if err == gorm.ErrRecordNotFound {
		return nil, models.NewValidationError("annotation group with ID '" + groupID + "' does not exist")
	}
	if err != nil {
		logger.Zap.Error("Failed to validate annotation group ID", logger.String("groupID", groupID), logger.Error(err))
		return nil, err
	}

	// Check if annotation group is discontinued
	if existingGroup.Discontinued {
		return nil, models.NewConflictError("annotation group with ID '" + groupID + "' is discontinued and cannot accept new items")
	}

	items := []models.AnnotationGroupItem{}

	// Check for existing combinations first (enforce unique constraint at application level)
	for _, sessionID := range sessionIDs {
		var existingItem models.AnnotationGroupItem
		err := cas.clickhouseDB.Where("group_id = ? AND session_id = ?", groupID, sessionID).First(&existingItem).Error
		if err == nil {
			// Combination already exists
			return nil, models.NewConflictError("annotation group item with this group_id and session_id combination already exists")
		}
		if err != gorm.ErrRecordNotFound {
			// Database error occurred
			logger.Zap.Error("Failed to check annotation group item uniqueness", logger.Error(err))
			return nil, err
		}

		item := models.AnnotationGroupItem{
			GroupID:   groupID,
			SessionID: sessionID,
		}
		items = append(items, item)
	}

	// Bulk insert
	result := cas.clickhouseDB.Create(&items)
	if result.Error != nil {
		logger.Zap.Error("Failed to create annotation group items", logger.Error(result.Error))
		return nil, result.Error
	}

	// Reload inserted items so their IDs and timestamps are populated
	var persistedItems []models.AnnotationGroupItem
	if err := cas.clickhouseDB.
		Where("group_id = ? AND session_id IN ?", groupID, sessionIDs).
		Find(&persistedItems).Error; err != nil {
		logger.Zap.Error("Failed to reload annotation group items after insert", logger.Error(err))
		return nil, err
	}

	persistedBySession := make(map[string]models.AnnotationGroupItem, len(persistedItems))
	for _, item := range persistedItems {
		persistedBySession[item.SessionID] = item
	}

	orderedItems := make([]models.AnnotationGroupItem, 0, len(sessionIDs))
	for _, sessionID := range sessionIDs {
		if item, ok := persistedBySession[sessionID]; ok {
			orderedItems = append(orderedItems, item)
		}
	}

	if len(orderedItems) != len(sessionIDs) {
		logger.Zap.Warn(
			"Mismatch when reloading annotation group items after insert",
			logger.String("group_id", groupID),
			logger.Int("requested", len(sessionIDs)),
			logger.Int("reloaded", len(orderedItems)),
		)
	}

	return orderedItems, nil
}

func (cas *ClickhouseAnnotationService) GetAnnotationGroupItems(groupID string, page, limit int) ([]models.AnnotationGroupItem, int, error) {
	var items []models.AnnotationGroupItem
	var total int64

	query := cas.clickhouseDB.Model(&models.AnnotationGroupItem{}).Where("group_id = ?", groupID)

	// Get total count
	if err := query.Count(&total).Error; err != nil {
		logger.Zap.Error("Failed to count annotation group items", logger.Error(err))
		return nil, 0, err
	}

	// Get paginated results
	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		logger.Zap.Error("Failed to get annotation group items", logger.Error(err))
		return nil, 0, err
	}

	return items, int(total), nil
}

func (cas *ClickhouseAnnotationService) DeleteAnnotationGroupItem(groupID, itemID string) error {
	// Check if any annotations are linked to this group item
	var annotationCount int64
	if err := cas.clickhouseDB.Model(&models.Annotation{}).Where("group_item_id = ?", itemID).Count(&annotationCount).Error; err != nil {
		logger.Zap.Error("Failed to check annotations for group item", logger.Error(err))
		return models.NewInternalError("failed to check annotations for group item", err)
	}

	if annotationCount > 0 {
		return models.NewConflictError("Cannot delete annotation group item: still referenced by annotations")
	}

	result := cas.clickhouseDB.Where("id = ? AND group_id = ?", itemID, groupID).Delete(&models.AnnotationGroupItem{})
	if result.Error != nil {
		logger.Zap.Error("Failed to delete annotation group item", logger.Error(result.Error))
		return models.NewInternalError("failed to delete annotation group item", result.Error)
	}

	if result.RowsAffected == 0 {
		return models.NewNotFoundError("annotation group item not found")
	}

	return nil
}

// Consensus computation structures
type ConsensusResult struct {
	ConsensusValue interface{} `json:"consensus_value"`
	HasConsensus   bool        `json:"has_consensus"`
	Values         []string    `json:"values"`
	Reviewers      []string    `json:"reviewers"`
	AgreementScore float64     `json:"agreement_score"`
	AnnotationType string      `json:"annotation_type"`
}

type ReviewerStatistics struct {
	TotalAnnotations int     `json:"total_annotations"`
	Agreements       int     `json:"agreements"`
	AgreementRate    float64 `json:"agreement_rate"`
}

type AnnotationTypeStatistics struct {
	AnnotationTypeName      string        `json:"annotation_type_name"`
	AnnotationTypeType      string        `json:"annotation_type_type"`
	TotalSessions           int           `json:"total_sessions"`
	ConsensusSessions       int           `json:"consensus_sessions"`
	NoConsensusSessions     int           `json:"no_consensus_sessions"`
	HighAgreementSessions   int           `json:"high_agreement_sessions"`
	TotalAnnotations        int           `json:"total_annotations"`
	TotalAgreements         int           `json:"total_agreements"`
	QualityScore            float64       `json:"quality_score"`
	AverageAgreementScore   float64       `json:"average_agreement_score"`
	ConsensusRate           float64       `json:"consensus_rate"`
	NoConsensusRate         float64       `json:"no_consensus_rate"`
	HighAgreementRate       float64       `json:"high_agreement_rate"`
	ConsensusValues         []interface{} `json:"consensus_values"`
	NoConsensusSessionsList []string      `json:"no_consensus_sessions_list"`
}

type ConfusionMatrix struct {
	TotalItems               int                                 `json:"total_items"`
	HighAgreementItems       int                                 `json:"high_agreement_items"`
	NoConsensusItems         int                                 `json:"no_consensus_items"`
	NoConsensusSessions      []string                            `json:"no_consensus_sessions"`
	HighAgreementRate        float64                             `json:"high_agreement_rate"`
	NoConsensusRate          float64                             `json:"no_consensus_rate"`
	AnnotationTypeStatistics map[string]AnnotationTypeStatistics `json:"annotation_type_statistics"`
	Summary                  string                              `json:"summary"`
	PerTypeSummary           map[string]string                   `json:"per_type_summary"`
}

// Consensus

func (cas *ClickhouseAnnotationService) ComputeConsensus(groupID string, method string) (*models.AnnotationConsensus, error) {
	// Validate method parameter
	if method == "" {
		method = "majority" // Default method
	}
	if method != "majority" {
		return nil, models.NewValidationError("unsupported consensus method '" + method + "'. Only 'majority' is currently supported")
	}

	// Validate foreign key constraint: group_id must exist
	var existingGroup models.AnnotationGroup
	err := cas.clickhouseDB.Where("id = ?", groupID).First(&existingGroup).Error
	if err == gorm.ErrRecordNotFound {
		return nil, models.NewValidationError("annotation group with ID '" + groupID + "' does not exist")
	}
	if err != nil {
		logger.Zap.Error("Failed to validate annotation group ID", logger.String("groupID", groupID), logger.Error(err))
		return nil, err
	}

	// Get group items (sessions)
	var items []models.AnnotationGroupItem
	err = cas.clickhouseDB.Where("group_id = ?", groupID).Find(&items).Error
	if err != nil {
		logger.Zap.Error("Failed to get group items", logger.Error(err))
		return nil, err
	}

	if len(items) == 0 {
		return nil, models.NewValidationError("no items found for group " + groupID)
	}

	// Get all annotations for sessions in this group, filtered by annotation types in the group
	sessionIDs := make([]string, len(items))
	for i, item := range items {
		sessionIDs[i] = item.SessionID
	}

	var allAnnotations []models.Annotation
	query := cas.clickhouseDB.Where("session_id IN ? AND annotation_type_id IN ?", sessionIDs, existingGroup.AnnotationTypeIDs)
	err = query.Find(&allAnnotations).Error
	if err != nil {
		logger.Zap.Error("Failed to get annotations for group", logger.Error(err))
		return nil, err
	}

	if len(allAnnotations) == 0 {
		return nil, models.NewValidationError("no annotations found for group " + groupID)
	}

	// Compute consensus using majority voting
	consensus, err := cas.computeMajorityConsensus(groupID, method, existingGroup, allAnnotations)
	if err != nil {
		logger.Zap.Error("Failed to compute consensus", logger.Error(err))
		return nil, err
	}

	// Check if we need to delete old consensus reports due to max_report limit
	err = cas.enforceMaxReportLimit(groupID, existingGroup.MaxReport)
	if err != nil {
		logger.Zap.Error("Failed to enforce max report limit", logger.Error(err))
		// Continue with creation even if cleanup fails
	}

	// Save consensus to database
	result := cas.clickhouseDB.Create(consensus)
	if result.Error != nil {
		logger.Zap.Error("Failed to create consensus report", logger.Error(result.Error))
		return nil, result.Error
	}

	// Reload the consensus from database to get the auto-generated fields (id, creation_date)
	var reloadedConsensus models.AnnotationConsensus
	if err := cas.clickhouseDB.Where("group_id = ? AND method = ?", groupID, method).
		Order("creation_date DESC").
		First(&reloadedConsensus).Error; err != nil {
		logger.Zap.Error("Failed to reload consensus after creation", logger.Error(err))
		// Return the original consensus even if reload fails
		return consensus, nil
	}

	return &reloadedConsensus, nil
}

// computeMajorityConsensus implements the majority voting consensus algorithm
func (cas *ClickhouseAnnotationService) computeMajorityConsensus(groupID string, method string, group models.AnnotationGroup, annotations []models.Annotation) (*models.AnnotationConsensus, error) {
	// Group annotations by (observation_id, observation_type, annotation_type_id)
	// This ensures that comparison between reviewers is based on the same observation and annotation type
	annotationGroups := make(map[string]map[string]map[string][]models.Annotation)
	for _, ann := range annotations {
		observationID := ann.ObservationID
		observationType := ann.ObservationType
		typeID := ann.AnnotationTypeID

		if annotationGroups[observationID] == nil {
			annotationGroups[observationID] = make(map[string]map[string][]models.Annotation)
		}
		if annotationGroups[observationID][observationType] == nil {
			annotationGroups[observationID][observationType] = make(map[string][]models.Annotation)
		}
		annotationGroups[observationID][observationType][typeID] = append(annotationGroups[observationID][observationType][typeID], ann)
	}

	// Initialize tracking variables
	consensusResults := make(map[string]ConsensusResult)     // key: observation_id:observation_type:annotation_type_id
	reviewerContributions := make(map[string]map[string]int) // reviewer_id -> {"total": x, "agreements": y}

	// Track structured data for new fields
	consensusValuesList := []models.ConsensusValue{}
	noConsensusValuesList := []models.NoConsensusValue{}

	// Initialize reviewer contributions tracking
	for _, ann := range annotations {
		if reviewerContributions[ann.ReviewerID] == nil {
			reviewerContributions[ann.ReviewerID] = map[string]int{"total": 0, "agreements": 0}
		}
	}

	// Get annotation types for processing
	annotationTypes := make(map[string]*models.AnnotationType)
	for _, typeID := range group.AnnotationTypeIDs {
		var annotationType models.AnnotationType
		err := cas.clickhouseDB.Where("id = ?", typeID).First(&annotationType).Error
		if err == nil {
			annotationTypes[typeID] = &annotationType
		}
	}

	// Variables for tracking annotation type statistics grouped by (annotation_type_id, observation_type)
	typeStatsMap := make(map[string]*models.AnnotationTypeStatistic)

	// Process each observation/observation-type/annotation-type combination
	for observationID, observationData := range annotationGroups {
		for observationType, typeData := range observationData {
			for typeID, observations := range typeData {
				if len(observations) < 2 {
					continue // Need at least 2 annotations for consensus
				}

				annotationType := annotationTypes[typeID]
				if annotationType == nil {
					continue
				}

				// Create key for grouping by (annotation_type_id, observation_type)
				typeStatsKey := typeID + ":" + observationType

				// Initialize stats for this group if not exists
				if _, exists := typeStatsMap[typeStatsKey]; !exists {
					typeStatsMap[typeStatsKey] = &models.AnnotationTypeStatistic{
						AnnotationTypeID:   typeID,
						AnnotationTypeName: annotationType.Name,
						AnnotationTypeType: annotationType.Type,
						ObservationType:    observationType,
						SessionsCount:      0,
						Consensus:          0,
						NoConsensus:        0,
						QualityScore:       0.0,
						ConsensusRate:      0.0,
						ConsensusValues:    []interface{}{},
					}
				}

				currentStats := typeStatsMap[typeStatsKey]

				// Extract values and reviewers
				values := make([]string, 0, len(observations))
				reviewers := make([]string, 0, len(observations))

				for _, ann := range observations {
					if ann.AnnotationValue != "" {
						values = append(values, ann.AnnotationValue)
						reviewers = append(reviewers, ann.ReviewerID)
					}
				}

				if len(values) == 0 {
					continue
				}

				// Increment session count for this type/observation combination
				currentStats.SessionsCount++

				// Compute consensus based on annotation type
				var consensusValue interface{}
				var hasConsensus bool
				var err error

				switch annotationType.Type {
				case "boolean":
					consensusValue, hasConsensus, err = cas.computeBooleanConsensus(values)
				case "categorical":
					consensusValue, hasConsensus, err = cas.computeCategoricalConsensus(values)
				case "numerical":
					consensusValue, hasConsensus, err = cas.computeNumericalConsensus(values)
				default:
					continue
				}

				if err != nil {
					logger.Zap.Error("Error computing consensus", logger.Error(err))
					continue
				}

				if hasConsensus {
					// Update aggregated statistics
					currentStats.Consensus++

					// Add consensus value to the list for this type
					currentStats.ConsensusValues = append(currentStats.ConsensusValues, consensusValue)

					// Add to consensus values list
					sessionID := observations[0].SessionID
					consensusValuesList = append(consensusValuesList, models.ConsensusValue{
						SessionID:     sessionID,
						ObservationID: observationID,
						Value:         consensusValue,
					})

					// Count agreements for quality score
					for i, value := range values {
						reviewer := reviewers[i]
						reviewerContributions[reviewer]["total"]++
						if cas.valuesMatch(value, consensusValue, annotationType.Type) {
							reviewerContributions[reviewer]["agreements"]++
						}
					}
				} else {
					// Update aggregated statistics
					currentStats.NoConsensus++

					// Add to no consensus values list
					sessionID := observations[0].SessionID
					annotationValues := make([]interface{}, len(values))
					for i, v := range values {
						var parsedValue interface{}
						if err := json.Unmarshal([]byte(v), &parsedValue); err == nil {
							annotationValues[i] = parsedValue
						} else {
							annotationValues[i] = v
						}
					}

					noConsensusValuesList = append(noConsensusValuesList, models.NoConsensusValue{
						SessionID:     sessionID,
						ObservationID: observationID,
						Values:        annotationValues,
					})

					// Still count total annotations for reviewers
					for _, reviewer := range reviewers {
						reviewerContributions[reviewer]["total"]++
					}
				}

				// Store consensus result with updated key format
				key := observationID + ":" + observationType + ":" + typeID
				consensusResults[key] = ConsensusResult{
					ConsensusValue: consensusValue,
					HasConsensus:   hasConsensus,
					Values:         values,
					Reviewers:      reviewers,
					AnnotationType: annotationType.Name,
				}
			}
		}
	}

	// Finalize annotation type statistics - calculate rates and quality scores
	annotationTypeStatsList := []models.AnnotationTypeStatistic{}
	for _, stats := range typeStatsMap {
		// Calculate consensus rate
		if stats.SessionsCount > 0 {
			stats.ConsensusRate = float64(stats.Consensus) / float64(stats.SessionsCount) * 100
		}

		// Calculate quality score for this type/observation combination
		// This is a simplified calculation - in a real scenario you might want more sophisticated logic
		if stats.SessionsCount > 0 {
			stats.QualityScore = float64(stats.Consensus) / float64(stats.SessionsCount) * 100
		}

		annotationTypeStatsList = append(annotationTypeStatsList, *stats)
	} // Calculate overall quality score
	totalAgreements := 0
	totalAnnotations := 0
	for _, counts := range reviewerContributions {
		totalAgreements += counts["agreements"]
		totalAnnotations += counts["total"]
	}

	qualityScore := 0.0
	if totalAnnotations > 0 {
		qualityScore = float64(totalAgreements) / float64(totalAnnotations) * 100
	}

	// Generate reviewer statistics - this becomes annotation_statistics
	annotationStatistics := make(map[string]interface{})
	for reviewerID, counts := range reviewerContributions {
		agreementRate := 0.0
		if counts["total"] > 0 {
			agreementRate = float64(counts["agreements"]) / float64(counts["total"]) * 100
		}
		annotationStatistics[reviewerID] = map[string]interface{}{
			"total_annotations": counts["total"],
			"agreements":        counts["agreements"],
			"agreement_rate":    agreementRate,
		}
	}

	// Helper function to convert data to JSONRawMessage
	convertToJSONRaw := func(data interface{}) *models.JSONRawMessage {
		if data == nil {
			return nil
		}
		jsonBytes, err := json.Marshal(data)
		if err != nil {
			return nil
		}
		raw := models.JSONRawMessage(jsonBytes)
		return &raw
	}

	// Create consensus record
	consensus := &models.AnnotationConsensus{
		GroupID:                  groupID,
		Method:                   method,
		Valid:                    true,
		QualityScore:             qualityScore,
		AnnotationStatistics:     convertToJSONRaw(annotationStatistics),
		AnnotationTypeStatistics: convertToJSONRaw(annotationTypeStatsList),
		ConsensusValues:          convertToJSONRaw(consensusValuesList),
		NoConsensusValues:        convertToJSONRaw(noConsensusValuesList),
		ReviewersQualityScore:    convertToJSONRaw(annotationStatistics),
		ReviewersStats:           convertToJSONRaw(annotationStatistics),
	}

	return consensus, nil
}

// Helper methods for consensus computation

// computeBooleanConsensus computes boolean consensus using majority vote
func (cas *ClickhouseAnnotationService) computeBooleanConsensus(values []string) (interface{}, bool, error) {
	trueCount := 0
	totalCount := len(values)

	for _, value := range values {
		// Parse JSON boolean value
		var boolVal bool
		err := json.Unmarshal([]byte(value), &boolVal)
		if err != nil {
			logger.Zap.Error("Failed to parse boolean value", logger.String("value", value), logger.Error(err))
			continue
		}
		if boolVal {
			trueCount++
		}
	}

	// Check if there's a clear majority (> 50%)
	if trueCount > totalCount/2 {
		return true, true, nil
	} else if trueCount < totalCount/2 {
		return false, true, nil
	} else {
		// Tie - no consensus
		return nil, false, nil
	}
}

// computeCategoricalConsensus computes categorical consensus using majority vote
func (cas *ClickhouseAnnotationService) computeCategoricalConsensus(values []string) (interface{}, bool, error) {
	// Count occurrences of each value
	counter := make(map[string]int)
	totalCount := len(values)

	for _, value := range values {
		// Parse JSON string value
		var strVal string
		err := json.Unmarshal([]byte(value), &strVal)
		if err != nil {
			logger.Zap.Error("Failed to parse categorical value", logger.String("value", value), logger.Error(err))
			continue
		}
		counter[strVal]++
	}

	// Find most common value
	var mostCommon string
	maxCount := 0
	for value, count := range counter {
		if count > maxCount {
			maxCount = count
			mostCommon = value
		}
	}

	// Check if the most common value has majority (> 50%)
	if maxCount > totalCount/2 {
		return mostCommon, true, nil
	} else {
		// No clear majority
		return nil, false, nil
	}
}

// computeNumericalConsensus computes numerical consensus using median
func (cas *ClickhouseAnnotationService) computeNumericalConsensus(values []string) (interface{}, bool, error) {
	// Parse numerical values
	nums := make([]float64, 0, len(values))
	for _, value := range values {
		var numVal float64
		err := json.Unmarshal([]byte(value), &numVal)
		if err != nil {
			logger.Zap.Error("Failed to parse numerical value", logger.String("value", value), logger.Error(err))
			continue
		}
		nums = append(nums, numVal)
	}

	if len(nums) == 0 {
		return nil, false, fmt.Errorf("no valid numerical values")
	}

	// Calculate median
	sort.Float64s(nums)
	var median float64
	n := len(nums)
	if n%2 == 0 {
		median = (nums[n/2-1] + nums[n/2]) / 2
	} else {
		median = nums[n/2]
	}

	// Check if most values are close to the median
	closeCount := 0
	for _, num := range nums {
		if cas.numericalValuesMatch(num, median) {
			closeCount++
		}
	}

	hasConsensus := closeCount > len(nums)/2
	return median, hasConsensus, nil
}

// valuesMatch checks if two values match based on annotation type
func (cas *ClickhouseAnnotationService) valuesMatch(value1Str string, value2 interface{}, annotationType string) bool {
	switch annotationType {
	case "boolean":
		var value1 bool
		err := json.Unmarshal([]byte(value1Str), &value1)
		if err != nil {
			return false
		}
		value2Bool, ok := value2.(bool)
		if !ok {
			return false
		}
		return value1 == value2Bool

	case "categorical":
		var value1 string
		err := json.Unmarshal([]byte(value1Str), &value1)
		if err != nil {
			return false
		}
		value2Str, ok := value2.(string)
		if !ok {
			return false
		}
		return value1 == value2Str

	case "numerical":
		var value1 float64
		err := json.Unmarshal([]byte(value1Str), &value1)
		if err != nil {
			return false
		}
		value2Float, ok := value2.(float64)
		if !ok {
			return false
		}
		return cas.numericalValuesMatch(value1, value2Float)
	}
	return false
}

// numericalValuesMatch checks if two numerical values are within 10% of each other
func (cas *ClickhouseAnnotationService) numericalValuesMatch(value1, value2 float64) bool {
	if value2 == 0 {
		return math.Abs(value1) < 0.1
	}
	return math.Abs(value1-value2)/math.Abs(value2) < 0.1
}

func (cas *ClickhouseAnnotationService) GetConsensusReports(groupID string, page, limit int) ([]models.AnnotationConsensus, int, error) {
	// First, verify that the annotation group exists
	_, err := cas.GetAnnotationGroupByID(groupID)
	if err != nil {
		// GetAnnotationGroupByID already returns proper ServiceError for not found cases
		return nil, 0, err
	}

	var reports []models.AnnotationConsensus
	var total int64

	query := cas.clickhouseDB.Model(&models.AnnotationConsensus{}).Where("group_id = ?", groupID)

	// Get total count
	if err := query.Count(&total).Error; err != nil {
		logger.Zap.Error("Failed to count consensus reports", logger.Error(err))
		return nil, 0, models.NewInternalError("failed to count consensus reports", err)
	}

	// Get paginated results
	offset := (page - 1) * limit
	if err := query.Offset(offset).Limit(limit).Order("creation_date DESC").Find(&reports).Error; err != nil {
		logger.Zap.Error("Failed to get consensus reports", logger.Error(err))
		return nil, 0, models.NewInternalError("failed to get consensus reports", err)
	}

	return reports, int(total), nil
}

func (cas *ClickhouseAnnotationService) GetConsensusReport(groupID, consensusID string) (*models.AnnotationConsensus, error) {
	var consensus models.AnnotationConsensus

	result := cas.clickhouseDB.Where("id = ? AND group_id = ?", consensusID, groupID).First(&consensus)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError("consensus report not found")
		}
		logger.Zap.Error("Failed to get consensus report", logger.Error(result.Error))
		return nil, models.NewInternalError("failed to get consensus report", result.Error)
	}

	return &consensus, nil
}

func (cas *ClickhouseAnnotationService) DeleteConsensusReport(groupID, consensusID string) error {
	result := cas.clickhouseDB.Where("id = ? AND group_id = ?", consensusID, groupID).Delete(&models.AnnotationConsensus{})
	if result.Error != nil {
		logger.Zap.Error("Failed to delete consensus report", logger.Error(result.Error))
		return models.NewInternalError("failed to delete consensus report", result.Error)
	}

	if result.RowsAffected == 0 {
		return models.NewNotFoundError("consensus report not found")
	}

	return nil
}

// enforceMaxReportLimit ensures that the number of consensus reports doesn't exceed max_report limit
// If the limit would be exceeded, it deletes the oldest report(s)
func (cas *ClickhouseAnnotationService) enforceMaxReportLimit(groupID string, maxReport int) error {
	// Count existing consensus reports for this group
	var count int64
	result := cas.clickhouseDB.Model(&models.AnnotationConsensus{}).Where("group_id = ?", groupID).Count(&count)
	if result.Error != nil {
		return result.Error
	}

	// If we're at or above the limit, delete the oldest report
	if count >= int64(maxReport) {
		// Find the oldest consensus report
		var oldestConsensus models.AnnotationConsensus
		result := cas.clickhouseDB.Where("group_id = ?", groupID).
			Order("creation_date ASC").
			First(&oldestConsensus)

		if result.Error != nil && result.Error != gorm.ErrRecordNotFound {
			return result.Error
		}

		if result.Error != gorm.ErrRecordNotFound {
			// Delete the oldest report
			deleteResult := cas.clickhouseDB.Where("id = ? AND group_id = ?", oldestConsensus.ID, groupID).
				Delete(&models.AnnotationConsensus{})
			if deleteResult.Error != nil {
				logger.Zap.Error("Failed to delete oldest consensus report",
					logger.String("group_id", groupID),
					logger.String("consensus_id", oldestConsensus.ID),
					logger.Error(deleteResult.Error))
				return deleteResult.Error
			}

			logger.Zap.Info("Deleted oldest consensus report to enforce max_report limit",
				logger.String("group_id", groupID),
				logger.String("deleted_consensus_id", oldestConsensus.ID),
				logger.Int("max_report", maxReport))
		}
	}

	return nil
}

// Annotation Dataset methods

// CreateAnnotationDataset creates a new annotation dataset
func (cas *ClickhouseAnnotationService) CreateAnnotationDataset(dataset *models.AnnotationDataset) (*models.AnnotationDataset, error) {
	// Check if dataset name already exists
	var existing models.AnnotationDataset
	result := cas.clickhouseDB.Where("name = ?", dataset.Name).First(&existing)
	if result.Error == nil {
		return nil, models.NewValidationError(fmt.Sprintf("Dataset with name '%s' already exists", dataset.Name))
	}
	if result.Error != gorm.ErrRecordNotFound {
		logger.Zap.Error("Error checking dataset name uniqueness", logger.Error(result.Error))
		return nil, result.Error
	}

	// Use raw SQL to insert without specifying ID, letting ClickHouse generate it
	// Format tags as ClickHouse array format ['tag1', 'tag2'] instead of JSON
	var tagsStr string
	if len(dataset.Tags) == 0 {
		tagsStr = "[]"
	} else {
		tagParts := make([]string, len(dataset.Tags))
		for i, tag := range dataset.Tags {
			// Escape single quotes in tags and wrap in single quotes
			escapedTag := strings.ReplaceAll(tag, "'", "\\'")
			tagParts[i] = "'" + escapedTag + "'"
		}
		tagsStr = "[" + strings.Join(tagParts, ", ") + "]"
	}

	insertSQL := "INSERT INTO annotation_datasets (name, tags) VALUES (?, ?)"
	result = cas.clickhouseDB.Exec(insertSQL, dataset.Name, tagsStr)
	if result.Error != nil {
		logger.Zap.Error("Error creating annotation dataset", logger.Error(result.Error))
		return nil, result.Error
	}

	// Query back the inserted record to get the generated ID and creation_date
	var insertedDataset models.AnnotationDataset
	err := cas.clickhouseDB.Where("name = ?", dataset.Name).
		Order("creation_date DESC").
		First(&insertedDataset).Error

	if err != nil {
		logger.Zap.Error("Failed to retrieve created annotation dataset", logger.Error(err))
		return nil, err
	}

	logger.Zap.Info("Created annotation dataset", logger.String("id", insertedDataset.ID), logger.String("name", insertedDataset.Name))
	return &insertedDataset, nil
}

// GetAnnotationDatasets retrieves annotation datasets with optional filtering and pagination
func (cas *ClickhouseAnnotationService) GetAnnotationDatasets(page, limit int, tags, name *string) ([]models.AnnotationDataset, int, error) {
	var datasets []models.AnnotationDataset
	var total int64

	query := cas.clickhouseDB.Model(&models.AnnotationDataset{})

	// Apply filters
	if name != nil && *name != "" {
		query = query.Where("LOWER(name) LIKE ?", "%"+strings.ToLower(*name)+"%")
	}

	if tags != nil && *tags != "" {
		tagList := strings.Split(*tags, ",")
		for _, tag := range tagList {
			tag = strings.TrimSpace(tag)
			if tag != "" {
				query = query.Where("hasAny(tags, [?])", tag)
			}
		}
	}

	// Get total count
	countResult := query.Count(&total)
	if countResult.Error != nil {
		logger.Zap.Error("Error counting annotation datasets", logger.Error(countResult.Error))
		return nil, 0, countResult.Error
	}

	// Apply pagination and order
	offset := (page - 1) * limit
	result := query.Order("creation_date DESC").Offset(offset).Limit(limit).Find(&datasets)
	if result.Error != nil {
		logger.Zap.Error("Error retrieving annotation datasets", logger.Error(result.Error))
		return nil, 0, result.Error
	}

	return datasets, int(total), nil
}

// GetAnnotationDatasetByID retrieves a dataset by ID
func (cas *ClickhouseAnnotationService) GetAnnotationDatasetByID(id string) (*models.AnnotationDataset, error) {
	var dataset models.AnnotationDataset
	result := cas.clickhouseDB.Where("id = ?", id).First(&dataset)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, models.NewNotFoundError(fmt.Sprintf("Dataset with ID '%s' not found", id))
		}
		logger.Zap.Error("Error retrieving annotation dataset", logger.String("id", id), logger.Error(result.Error))
		return nil, result.Error
	}

	return &dataset, nil
}

// DeleteAnnotationDataset deletes a dataset and all its items
func (cas *ClickhouseAnnotationService) DeleteAnnotationDataset(id string) error {
	// First check if dataset exists
	_, err := cas.GetAnnotationDatasetByID(id)
	if err != nil {
		return err
	}

	// Delete all items first
	itemsResult := cas.clickhouseDB.Where("dataset_id = ?", id).Delete(&models.AnnotationDatasetItem{})
	if itemsResult.Error != nil {
		logger.Zap.Error("Error deleting annotation dataset items", logger.String("dataset_id", id), logger.Error(itemsResult.Error))
		return itemsResult.Error
	}

	// Delete the dataset
	result := cas.clickhouseDB.Where("id = ?", id).Delete(&models.AnnotationDataset{})
	if result.Error != nil {
		logger.Zap.Error("Error deleting annotation dataset", logger.String("id", id), logger.Error(result.Error))
		return result.Error
	}

	logger.Zap.Info("Deleted annotation dataset", logger.String("id", id), logger.Int64("items_deleted", itemsResult.RowsAffected))
	return nil
}

// GetAnnotationDatasetItemCount gets the count of items in a dataset
func (cas *ClickhouseAnnotationService) GetAnnotationDatasetItemCount(datasetID string) (int, error) {
	var count int64
	result := cas.clickhouseDB.Model(&models.AnnotationDatasetItem{}).Where("dataset_id = ?", datasetID).Count(&count)
	if result.Error != nil {
		logger.Zap.Error("Error counting annotation dataset items", logger.String("dataset_id", datasetID), logger.Error(result.Error))
		return 0, result.Error
	}

	return int(count), nil
}

// ImportAnnotationDatasetItems imports items into a dataset
func (cas *ClickhouseAnnotationService) ImportAnnotationDatasetItems(datasetID string, items []models.AnnotationDatasetItemCreate) ([]string, map[int]string, error) {
	// First check if dataset exists
	_, err := cas.GetAnnotationDatasetByID(datasetID)
	if err != nil {
		return nil, nil, err
	}

	var successfulItems []string
	errors := make(map[int]string)

	for i, itemCreate := range items {
		// Check for uniqueness constraint: (dataset_id, session_id, session_date)
		var existing models.AnnotationDatasetItem
		query := cas.clickhouseDB.Where("dataset_id = ? AND session_id = ?", datasetID, itemCreate.SessionID)

		if itemCreate.SessionDate != nil {
			query = query.Where("session_date = ?", itemCreate.SessionDate)
		} else {
			query = query.Where("session_date IS NULL")
		}

		result := query.First(&existing)
		if result.Error == nil {
			errors[i] = fmt.Sprintf("Item with session_id '%s' and session_date '%v' already exists in dataset", itemCreate.SessionID, itemCreate.SessionDate)
			continue
		}
		if result.Error != gorm.ErrRecordNotFound {
			logger.Zap.Error("Error checking dataset item uniqueness", logger.Error(result.Error))
			errors[i] = fmt.Sprintf("Error checking uniqueness: %v", result.Error)
			continue
		}

		// Create the item using raw SQL to let ClickHouse generate the ID
		item := itemCreate.ToAnnotationDatasetItem(datasetID)

		// Format tags as ClickHouse array format ['tag1', 'tag2'] instead of JSON
		var tagsStr string
		if len(item.Tags) == 0 {
			tagsStr = "[]"
		} else {
			tagParts := make([]string, len(item.Tags))
			for i, tag := range item.Tags {
				// Escape single quotes in tags and wrap in single quotes
				escapedTag := strings.ReplaceAll(tag, "'", "\\'")
				tagParts[i] = "'" + escapedTag + "'"
			}
			tagsStr = "[" + strings.Join(tagParts, ", ") + "]"
		}

		insertSQL := "INSERT INTO annotation_dataset_items (dataset_id, session_id, session_date, input, output, expected_output, tags) VALUES (?, ?, ?, ?, ?, ?, ?)"
		createResult := cas.clickhouseDB.Exec(insertSQL,
			item.DatasetID,
			item.SessionID,
			item.SessionDate,
			item.Input,
			item.Output,
			item.ExpectedOutput,
			tagsStr)

		if createResult.Error != nil {
			logger.Zap.Error("Error creating annotation dataset item", logger.Error(createResult.Error))
			errors[i] = fmt.Sprintf("Error creating item: %v", createResult.Error)
			continue
		}

		// Query back the inserted record to get the generated ID
		var insertedItem models.AnnotationDatasetItem
		queryBack := cas.clickhouseDB.Where("dataset_id = ? AND session_id = ?", datasetID, itemCreate.SessionID)

		if itemCreate.SessionDate != nil {
			queryBack = queryBack.Where("session_date = ?", itemCreate.SessionDate)
		} else {
			queryBack = queryBack.Where("session_date IS NULL")
		}

		err := queryBack.Order("creation_date DESC").First(&insertedItem).Error
		if err != nil {
			logger.Zap.Error("Failed to retrieve created annotation dataset item", logger.Error(err))
			errors[i] = fmt.Sprintf("Error retrieving created item: %v", err)
			continue
		}

		successfulItems = append(successfulItems, insertedItem.ID)
	}

	logger.Zap.Info("Imported annotation dataset items",
		logger.String("dataset_id", datasetID),
		logger.Int("total_items", len(items)),
		logger.Int("successful_items", len(successfulItems)),
		logger.Int("failed_items", len(errors)))

	return successfulItems, errors, nil
}

// GetAnnotationDatasetItems retrieves items from a dataset
func (cas *ClickhouseAnnotationService) GetAnnotationDatasetItems(datasetID string, itemIDs []string) (map[string]models.AnnotationDatasetItem, []string, error) {
	// First check if dataset exists
	_, err := cas.GetAnnotationDatasetByID(datasetID)
	if err != nil {
		return nil, nil, err
	}

	if len(itemIDs) > 50 {
		return nil, nil, models.NewValidationError("Cannot retrieve more than 50 items at once")
	}

	var items []models.AnnotationDatasetItem
	query := cas.clickhouseDB.Where("dataset_id = ?", datasetID)

	if len(itemIDs) > 0 {
		query = query.Where("id IN ?", itemIDs)
	}

	result := query.Find(&items)
	if result.Error != nil {
		logger.Zap.Error("Error retrieving annotation dataset items", logger.String("dataset_id", datasetID), logger.Error(result.Error))
		return nil, nil, result.Error
	}

	// Create response map
	data := make(map[string]models.AnnotationDatasetItem)
	foundIDs := make(map[string]bool)

	for _, item := range items {
		data[item.ID] = item
		foundIDs[item.ID] = true
	}

	// Find not found IDs
	var notFoundIDs []string
	if len(itemIDs) > 0 {
		for _, id := range itemIDs {
			if !foundIDs[id] {
				notFoundIDs = append(notFoundIDs, id)
			}
		}
	}

	return data, notFoundIDs, nil
}
