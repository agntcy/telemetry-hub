// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package http

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	services "github.com/agntcy/telemetry-hub/api-layer/pkg/services/interfaces"
	"github.com/gorilla/mux"
)

type AnnotationDatasetServer struct {
	AnnotationService services.AnnotationService
	Enabled           bool
}

// Dataset Handlers

// @Summary      Create annotation dataset
// @Description  Create a new annotation dataset
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        dataset body models.AnnotationDatasetCreate true "Dataset to create"
// @Success      201 {object} models.AnnotationDatasetResponse "Dataset created successfully"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      409 {object} ErrorResponse "Dataset name already exists"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets [post]
func (ads *AnnotationDatasetServer) CreateAnnotationDataset(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var createReq models.AnnotationDatasetCreate
	if err := json.NewDecoder(r.Body).Decode(&createReq); err != nil {
		ads.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	dataset := createReq.ToAnnotationDataset()
	createdDataset, err := ads.AnnotationService.CreateAnnotationDataset(dataset)
	if err != nil {
		ads.handleServiceError(w, err, "Error creating annotation dataset")
		return
	}

	response := createdDataset.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Location", fmt.Sprintf("/annotation-datasets/%s", createdDataset.ID))
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation datasets
// @Description  Get annotation datasets with optional filtering and pagination
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Param        tags query string false "Filter by tags (comma separated)"
// @Param        name query string false "Filter by dataset name (case insensitive LIKE search)"
// @Success      200 {object} models.PaginatedResponse "List of datasets"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets [get]
func (ads *AnnotationDatasetServer) GetAnnotationDatasets(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}

	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 || limit > 100 {
		limit = 50
	}

	tags := r.URL.Query().Get("tags")
	var tagsPtr *string
	if tags != "" {
		tagsPtr = &tags
	}

	name := r.URL.Query().Get("name")
	var namePtr *string
	if name != "" {
		namePtr = &name
	}

	datasets, total, err := ads.AnnotationService.GetAnnotationDatasets(page, limit, tagsPtr, namePtr)
	if err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotation datasets: %v", err))
		return
	}

	responses := make([]models.AnnotationDatasetResponse, len(datasets))
	for i, d := range datasets {
		responses[i] = d.ToResponse()
	}

	paginatedResponse := models.PaginatedResponse{
		Page:    page,
		Limit:   limit,
		Total:   total,
		HasNext: page*limit < total,
		HasPrev: page > 1,
		Data:    responses,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(paginatedResponse); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation dataset by ID
// @Description  Get annotation dataset by ID with item count
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        dataset-id path string true "Dataset ID"
// @Success      200 {object} models.AnnotationDatasetResponse "Dataset details"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Dataset not found"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets/{dataset-id} [get]
func (ads *AnnotationDatasetServer) GetAnnotationDataset(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	datasetID, ok := vars["dataset-id"]
	if !ok || datasetID == "" {
		ads.handleJSONError(w, http.StatusBadRequest, "Dataset ID is required")
		return
	}

	dataset, err := ads.AnnotationService.GetAnnotationDatasetByID(datasetID)
	if err != nil {
		ads.handleServiceError(w, err, "Error retrieving annotation dataset")
		return
	}

	// Get item count
	count, err := ads.AnnotationService.GetAnnotationDatasetItemCount(datasetID)
	if err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error getting item count: %v", err))
		return
	}

	response := dataset.ToResponseWithCount(count)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete annotation dataset
// @Description  Delete annotation dataset and all its items
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        dataset-id path string true "Dataset ID"
// @Success      204 "Dataset deleted successfully"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Dataset not found"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets/{dataset-id} [delete]
func (ads *AnnotationDatasetServer) DeleteAnnotationDataset(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	datasetID, ok := vars["dataset-id"]
	if !ok || datasetID == "" {
		ads.handleJSONError(w, http.StatusBadRequest, "Dataset ID is required")
		return
	}

	err := ads.AnnotationService.DeleteAnnotationDataset(datasetID)
	if err != nil {
		ads.handleServiceError(w, err, "Error deleting annotation dataset")
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary      Import items into dataset
// @Description  Import items into an annotation dataset
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        dataset-id path string true "Dataset ID"
// @Param        items body []models.AnnotationDatasetItemCreate true "Items to import"
// @Success      200 {object} models.ImportResponse "Import completed"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Dataset not found"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets/{dataset-id}/import [post]
func (ads *AnnotationDatasetServer) ImportDatasetItems(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	datasetID, ok := vars["dataset-id"]
	if !ok || datasetID == "" {
		ads.handleJSONError(w, http.StatusBadRequest, "Dataset ID is required")
		return
	}

	var items []models.AnnotationDatasetItemCreate
	if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
		ads.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	if len(items) == 0 {
		ads.handleJSONError(w, http.StatusBadRequest, "No items provided for import")
		return
	}

	successfulItems, errors, err := ads.AnnotationService.ImportAnnotationDatasetItems(datasetID, items)
	if err != nil {
		ads.handleServiceError(w, err, "Error importing dataset items")
		return
	}

	// Determine the state
	var state string
	if len(errors) == 0 {
		state = models.ImportStateCompleted
	} else if len(successfulItems) == 0 {
		state = models.ImportStateFailed
	} else {
		state = models.ImportStatePartial
	}

	response := models.ImportResponse{
		Name:   fmt.Sprintf("/annotation-datasets/%s", datasetID),
		Status: models.ImportStatus{State: state},
	}

	if len(errors) > 0 {
		response.Errors = errors
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get dataset items
// @Description  Get items from an annotation dataset
// @Tags         annotation-datasets
// @Accept       json
// @Produce      json
// @Param        dataset-id path string true "Dataset ID"
// @Param        item_ids query string false "Comma separated list of item IDs (max 50)"
// @Success      200 {object} models.DatasetItemsResponse "Dataset items"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Dataset not found"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-datasets/{dataset-id}/items [get]
func (ads *AnnotationDatasetServer) GetDatasetItems(w http.ResponseWriter, r *http.Request) {
	if !ads.Enabled {
		ads.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		ads.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	datasetID, ok := vars["dataset-id"]
	if !ok || datasetID == "" {
		ads.handleJSONError(w, http.StatusBadRequest, "Dataset ID is required")
		return
	}

	itemIDsParam := r.URL.Query().Get("item_ids")
	var itemIDs []string
	if itemIDsParam != "" {
		itemIDs = strings.Split(itemIDsParam, ",")
		// Trim spaces
		for i, id := range itemIDs {
			itemIDs[i] = strings.TrimSpace(id)
		}
		// Remove empty strings
		var filteredIDs []string
		for _, id := range itemIDs {
			if id != "" {
				filteredIDs = append(filteredIDs, id)
			}
		}
		itemIDs = filteredIDs

		if len(itemIDs) > 50 {
			ads.handleJSONError(w, http.StatusBadRequest, "Cannot retrieve more than 50 items at once")
			return
		}
	}

	data, notFoundIDs, err := ads.AnnotationService.GetAnnotationDatasetItems(datasetID, itemIDs)
	if err != nil {
		ads.handleServiceError(w, err, "Error retrieving dataset items")
		return
	}

	response := models.DatasetItemsResponse{
		Data:            data,
		NotFoundItemIDs: notFoundIDs,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// Error handling methods (same as in AnnotationServer)

// handleServiceError handles service errors and returns appropriate HTTP status codes with JSON responses
func (ads *AnnotationDatasetServer) handleServiceError(w http.ResponseWriter, err error, context string) {
	w.Header().Set("Content-Type", "application/json")

	var errorResponse ErrorResponse
	var statusCode int

	if serviceErr, ok := models.IsServiceError(err); ok {
		errorResponse.Error = true
		errorResponse.Reason = serviceErr.Error()

		switch {
		case serviceErr.IsNotFound():
			statusCode = http.StatusNotFound
		case serviceErr.IsValidation():
			statusCode = http.StatusBadRequest
		case serviceErr.IsConflict():
			statusCode = http.StatusConflict
		default:
			statusCode = http.StatusInternalServerError
		}
	} else {
		// Handle non-service errors as internal server errors
		errorResponse.Error = true
		errorResponse.Reason = err.Error()
		statusCode = http.StatusInternalServerError
	}

	errorResponse.Status = statusCode
	w.WriteHeader(statusCode)
	if err := json.NewEncoder(w).Encode(errorResponse); err != nil {
		ads.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode error response: %v", err))
		return
	}
}

// handleJSONError returns a JSON error response with the specified status code and message
func (ads *AnnotationDatasetServer) handleJSONError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	errorResponse := ErrorResponse{
		Error:  true,
		Status: statusCode,
		Reason: message,
	}
	w.WriteHeader(statusCode)
	if err := json.NewEncoder(w).Encode(errorResponse); err != nil {
		// Last resort - write plain text
		http.Error(w, "Failed to encode error response", http.StatusInternalServerError)
		return
	}
}