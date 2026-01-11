// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package http

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse/models"
	services "github.com/agntcy/telemetry-hub/api-layer/pkg/services/interfaces"
	"github.com/gorilla/mux"
)

type AnnotationServer struct {
	AnnotationService services.AnnotationService
	Enabled           bool
}

// ErrorResponse represents a JSON error response
type ErrorResponse struct {
	Error  bool   `json:"error"`
	Status int    `json:"status"`
	Reason string `json:"reason"`
}

// handleServiceError handles service errors and returns appropriate HTTP status codes with JSON responses
func (as *AnnotationServer) handleServiceError(w http.ResponseWriter, err error, context string) {
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode error response: %v", err))
		return
	}
}

// handleJSONError returns a JSON error response with the specified status code and message
func (as *AnnotationServer) handleJSONError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	errorResponse := ErrorResponse{
		Error:  true,
		Status: statusCode,
		Reason: message,
	}
	w.WriteHeader(statusCode)
	if err := json.NewEncoder(w).Encode(errorResponse); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode error response: %v", err))
		return
	}
}

// Annotation Types Handlers

// @Summary      Create annotation type
// @Description  Create a new annotation type
// @Tags         Annotation Types
// @Accept       json
// @Produce      json
// @Param        annotation_type body models.AnnotationTypeCreate true "Annotation type to create"
// @Success      201 {object} models.AnnotationTypeResponse "Annotation type created successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-types [post]
func (as *AnnotationServer) CreateAnnotationType(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var createReq models.AnnotationTypeCreate
	if err := json.NewDecoder(r.Body).Decode(&createReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	annotationType := createReq.ToAnnotationType()
	createdType, err := as.AnnotationService.CreateAnnotationType(annotationType)
	if err != nil {
		as.handleServiceError(w, err, "Error creating annotation type")
		return
	}

	response := createdType.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Location", fmt.Sprintf("/annotation-types/%s", createdType.ID))
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode error response: %v", err))
		return
	}
}

// @Summary      Get annotation types
// @Description  Get annotation types with optional group filter and pagination
// @Tags         Annotation Types
// @Accept       json
// @Produce      json
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Param        group_id query string false "Filter by annotation group ID"
// @Success      200 {object} models.PaginatedResponse "List of annotation types"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-types [get]
func (as *AnnotationServer) GetAnnotationTypes(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
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

	groupID := r.URL.Query().Get("group_id")
	var groupIDPtr *string
	if groupID != "" {
		groupIDPtr = &groupID
	}

	types, total, err := as.AnnotationService.GetAnnotationTypes(page, limit, groupIDPtr)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotation types: %v", err))
		return
	}

	responses := make([]models.AnnotationTypeResponse, len(types))
	for i, t := range types {
		responses[i] = t.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode error response: %v", err))
		return
	}
}

// @Summary      Get annotation type by ID
// @Description  Get annotation type by ID
// @Tags         Annotation Types
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Type ID"
// @Success      200 {object} models.AnnotationTypeResponse "Annotation type details"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-types/{id} [get]
func (as *AnnotationServer) GetAnnotationType(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation type ID is required")
		return
	}

	annotationType, err := as.AnnotationService.GetAnnotationTypeByID(id)
	if err != nil {
		as.handleServiceError(w, err, "Error fetching annotation type")
		return
	}

	response := annotationType.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Update annotation type
// @Description  Update annotation type by ID
// @Tags         Annotation Types
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Type ID"
// @Param        annotation_type body models.AnnotationTypeUpdate true "Annotation type updates"
// @Success      200 {object} models.AnnotationTypeResponse "Updated annotation type"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-types/{id} [put]
func (as *AnnotationServer) UpdateAnnotationType(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPut {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation type ID is required")
		return
	}

	var updateReq models.AnnotationTypeUpdate
	if err := json.NewDecoder(r.Body).Decode(&updateReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	updatedType, err := as.AnnotationService.UpdateAnnotationType(id, &updateReq)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error updating annotation type: %v", err))
		return
	}

	response := updatedType.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete annotation type
// @Description  Delete annotation type by ID
// @Tags         Annotation Types
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Type ID"
// @Success      200 {object} string "Annotation type deleted successfully"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Annotation type not found"
// @Failure      409 {object} ErrorResponse "Cannot delete - annotation type is still in use by annotations or groups"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-types/{id} [delete]
func (as *AnnotationServer) DeleteAnnotationType(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation type ID is required")
		return
	}

	err := as.AnnotationService.DeleteAnnotationType(id)
	if err != nil {
		as.handleServiceError(w, err, "deleting annotation type")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"message": "Annotation type deleted successfully"}); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// Annotations Handlers

// @Summary      Create annotation
// @Description  Create a new annotation
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        annotation body models.AnnotationCreate true "Annotation to create"
// @Success      201 {object} models.AnnotationResponse "Annotation created successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      409 {object} ErrorResponse "Conflict - annotation type is discontinued or annotation group is discontinued"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations [post]
func (as *AnnotationServer) CreateAnnotation(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var createReq models.AnnotationCreate
	if err := json.NewDecoder(r.Body).Decode(&createReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	// Validate the request
	if err := createReq.Validate(); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Validation error: %v", err))
		return
	}

	annotation := createReq.ToAnnotation()
	createdAnnotation, err := as.AnnotationService.CreateAnnotation(annotation)
	if err != nil {
		as.handleServiceError(w, err, "Error creating annotation")
		return
	}

	response := createdAnnotation.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
	w.Header().Set("Location", fmt.Sprintf("/annotations/%s", createdAnnotation.ID))
}

// @Summary      Get annotations
// @Description  Get annotations with optional filters and pagination
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Param        group_id query string false "Filter by annotation group ID"
// @Param        session_id query string false "Filter by session ID"
// @Param        reviewer_id query string false "Filter by reviewer ID"
// @Success      200 {object} models.PaginatedResponse "List of annotations"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations [get]
func (as *AnnotationServer) GetAnnotations(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
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

	groupID := r.URL.Query().Get("group_id")
	sessionID := r.URL.Query().Get("session_id")
	reviewerID := r.URL.Query().Get("reviewer_id")

	var groupIDPtr, sessionIDPtr, reviewerIDPtr *string
	if groupID != "" {
		groupIDPtr = &groupID
	}
	if sessionID != "" {
		sessionIDPtr = &sessionID
	}
	if reviewerID != "" {
		reviewerIDPtr = &reviewerID
	}

	annotations, total, err := as.AnnotationService.GetAnnotations(page, limit, groupIDPtr, sessionIDPtr, reviewerIDPtr)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotations: %v", err))
		return
	}

	responses := make([]models.AnnotationResponse, len(annotations))
	for i, a := range annotations {
		responses[i] = a.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotations by session ID
// @Description  Get annotations for a given session ID with optional pagination
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        session_id path string true "Session ID"
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Success      200 {object} models.PaginatedResponse "List of annotations"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations/session/{session_id} [get]
func (as *AnnotationServer) GetAnnotationsBySessionID(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	sessionID := vars["session_id"]
	if sessionID == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Session ID is required")
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

	annotations, total, err := as.AnnotationService.GetAnnotations(page, limit, nil, &sessionID, nil)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotations: %v", err))
		return
	}

	responses := make([]models.AnnotationResponse, len(annotations))
	for i, a := range annotations {
		responses[i] = a.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation by ID
// @Description  Get annotation by ID
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation ID"
// @Success      200 {object} models.AnnotationResponse "Annotation details"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations/{id} [get]
func (as *AnnotationServer) GetAnnotation(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation ID is required")
		return
	}

	annotation, err := as.AnnotationService.GetAnnotationByID(id)
	if err != nil {
		as.handleServiceError(w, err, "Error fetching annotation")
		return
	}

	response := annotation.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Update annotation
// @Description  Update annotation by ID
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation ID"
// @Param        annotation body models.AnnotationUpdate true "Annotation updates"
// @Success      200 {object} models.AnnotationResponse "Updated annotation"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations/{id} [put]
func (as *AnnotationServer) UpdateAnnotation(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPut {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation ID is required")
		return
	}

	var updateReq models.AnnotationUpdate
	if err := json.NewDecoder(r.Body).Decode(&updateReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	updatedAnnotation, err := as.AnnotationService.UpdateAnnotation(id, &updateReq)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error updating annotation: %v", err))
		return
	}

	response := updatedAnnotation.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete annotation
// @Description  Delete annotation by ID
// @Tags         Annotations
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation ID"
// @Success      200 {object} string "Annotation deleted successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotations/{id} [delete]
func (as *AnnotationServer) DeleteAnnotation(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation ID is required")
		return
	}

	err := as.AnnotationService.DeleteAnnotation(id)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error deleting annotation: %v", err))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"message": "Annotation deleted successfully"}); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// Annotation Groups Handlers

// @Summary      Create annotation group
// @Description  Create a new annotation group
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        annotation_group body models.AnnotationGroupCreate true "Annotation group to create"
// @Success      201 {object} models.AnnotationGroupResponse "Annotation group created successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      409 {object} ErrorResponse "Conflict - annotation type is discontinued"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups [post]
func (as *AnnotationServer) CreateAnnotationGroup(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var createReq models.AnnotationGroupCreate
	if err := json.NewDecoder(r.Body).Decode(&createReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	group := createReq.ToAnnotationGroup()
	createdGroup, err := as.AnnotationService.CreateAnnotationGroup(group)
	if err != nil {
		as.handleServiceError(w, err, "Error creating annotation group")
		return
	}

	response := createdGroup.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Location", fmt.Sprintf("/annotation-groups/%s", createdGroup.ID))
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation groups
// @Description  Get annotation groups with pagination
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Success      200 {object} models.PaginatedResponse "List of annotation groups"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups [get]
func (as *AnnotationServer) GetAnnotationGroups(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
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

	// Get optional name filter
	var name *string
	if nameParam := r.URL.Query().Get("name"); nameParam != "" {
		name = &nameParam
	}

	groups, total, err := as.AnnotationService.GetAnnotationGroups(page, limit, name)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotation groups: %v", err))
		return
	}

	responses := make([]models.AnnotationGroupResponse, len(groups))
	for i, g := range groups {
		responses[i] = g.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation group by ID
// @Description  Get annotation group by ID
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Success      200 {object} models.AnnotationGroupResponse "Annotation group details"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id} [get]
func (as *AnnotationServer) GetAnnotationGroup(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
		return
	}

	group, err := as.AnnotationService.GetAnnotationGroupByID(id)
	if err != nil {
		as.handleServiceError(w, err, "Error fetching annotation group")
		return
	}

	response := group.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Update annotation group
// @Description  Update annotation group by ID
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Param        annotation_group body models.AnnotationGroupUpdate true "Annotation group updates"
// @Success      200 {object} models.AnnotationGroupResponse "Updated annotation group"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id} [put]
func (as *AnnotationServer) UpdateAnnotationGroup(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPut {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
		return
	}

	var updateReq models.AnnotationGroupUpdate
	if err := json.NewDecoder(r.Body).Decode(&updateReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	updatedGroup, err := as.AnnotationService.UpdateAnnotationGroup(id, &updateReq)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error updating annotation group: %v", err))
		return
	}

	response := updatedGroup.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete annotation group
// @Description  Delete annotation group by ID
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Success      200 {object} string "Annotation group deleted successfully"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Annotation group not found"
// @Failure      409 {object} ErrorResponse "Cannot delete - annotation group is still in use by consensus reports or group items"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-groups/{id} [delete]
func (as *AnnotationServer) DeleteAnnotationGroup(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
		return
	}

	err := as.AnnotationService.DeleteAnnotationGroup(id)
	if err != nil {
		as.handleServiceError(w, err, "deleting annotation group")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"message": "Annotation group deleted successfully"}); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Create annotation group items
// @Description  Create annotation group items for a specific group
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Param        items body models.AnnotationGroupItemCreate true "Annotation group items to create"
// @Success      201 {array} models.AnnotationGroupItemResponse "Annotation group items created successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      409 {object} ErrorResponse "Conflict - annotation group is discontinued"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id}/items [post]
func (as *AnnotationServer) CreateAnnotationGroupItems(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
		return
	}

	var createReq models.AnnotationGroupItemCreate
	if err := json.NewDecoder(r.Body).Decode(&createReq); err != nil {
		as.handleJSONError(w, http.StatusBadRequest, fmt.Sprintf("Error decoding request body: %v", err))
		return
	}

	items, err := as.AnnotationService.CreateAnnotationGroupItems(id, createReq.SessionIDs)
	if err != nil {
		as.handleServiceError(w, err, "Error creating annotation group items")
		return
	}

	responses := make([]models.AnnotationGroupItemResponse, len(items))
	for i, item := range items {
		responses[i] = item.ToResponse()
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(responses); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get annotation group items
// @Description  Get annotation group items with pagination
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Success      200 {object} models.PaginatedResponse "List of annotation group items"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id}/items [get]
func (as *AnnotationServer) GetAnnotationGroupItems(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
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

	items, total, err := as.AnnotationService.GetAnnotationGroupItems(id, page, limit)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error fetching annotation group items: %v", err))
		return
	}

	responses := make([]models.AnnotationGroupItemResponse, len(items))
	for i, item := range items {
		responses[i] = item.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete annotation group item
// @Description  Delete annotation group item by ID
// @Tags         Annotation Groups
// @Accept       json
// @Produce      json
// @Param        id1 path string true "Annotation Group ID"
// @Param        id2 path string true "Annotation Group Item ID"
// @Success      200 {object} string "Annotation group item deleted successfully"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Annotation group item not found"
// @Failure      409 {object} ErrorResponse "Cannot delete - annotation group item is still in use by annotations"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-groups/{id1}/items/{id2} [delete]
func (as *AnnotationServer) DeleteAnnotationGroupItem(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	groupID := vars["id1"]
	itemID := vars["id2"]
	if groupID == "" || itemID == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Group ID and Item ID are required")
		return
	}

	err := as.AnnotationService.DeleteAnnotationGroupItem(groupID, itemID)
	if err != nil {
		as.handleServiceError(w, err, "Error deleting annotation group item")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"message": "Annotation group item deleted successfully"}); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// Consensus Handlers

// @Summary      Compute consensus
// @Description  Compute consensus for an annotation group
// @Tags         Annotation Group Consensus
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Param        method query string false "Consensus method (default: majority)"
// @Success      201 {object} models.AnnotationConsensusResponse "Consensus computed successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id}/consensus/compute [post]
func (as *AnnotationServer) ComputeConsensus(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodPost {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
		return
	}

	// Get method parameter from query string (default to "majority")
	method := r.URL.Query().Get("method")
	if method == "" {
		method = "majority"
	}

	// Validate the consensus method
	if !models.IsValidConsensusMethod(method) {
		as.handleJSONError(w, http.StatusBadRequest, "Invalid consensus method: must be 'majority'")
		return
	}

	consensus, err := as.AnnotationService.ComputeConsensus(id, method)
	if err != nil {
		as.handleServiceError(w, err, "Error computing consensus")
		return
	}

	response := consensus.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Location", fmt.Sprintf("/annotation-groups/%s/consensus/%s", id, consensus.ID))
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get consensus reports
// @Description  Get consensus reports for an annotation group with pagination
// @Tags         Annotation Group Consensus
// @Accept       json
// @Produce      json
// @Param        id path string true "Annotation Group ID"
// @Param        page query int false "Page number" default(1) minimum(1)
// @Param        limit query int false "Number of items per page" default(50) minimum(1) maximum(100)
// @Success      200 {object} models.PaginatedResponse "List of consensus reports"
// @Failure      400 {object} string "Bad request"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id}/consensus [get]
func (as *AnnotationServer) GetConsensusReports(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	id := vars["id"]
	if id == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Annotation group ID is required")
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

	reports, total, err := as.AnnotationService.GetConsensusReports(id, page, limit)
	if err != nil {
		as.handleServiceError(w, err, "fetching consensus reports")
		return
	}

	responses := make([]models.AnnotationConsensusResponse, len(reports))
	for i, report := range reports {
		responses[i] = report.ToResponse()
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
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Get consensus report
// @Description  Get specific consensus report by ID
// @Tags         Annotation Group Consensus
// @Accept       json
// @Produce      json
// @Param        id1 path string true "Annotation Group ID"
// @Param        id2 path string true "Consensus Report ID"
// @Success      200 {object} models.AnnotationConsensusResponse "Consensus report details"
// @Failure      400 {object} ErrorResponse "Bad request"
// @Failure      404 {object} ErrorResponse "Group or report not found"
// @Failure      500 {object} ErrorResponse "Internal server error"
// @Router       /annotation-groups/{id1}/consensus/{id2} [get]
func (as *AnnotationServer) GetConsensusReport(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodGet {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	groupID := vars["id1"]
	consensusID := vars["id2"]
	if groupID == "" || consensusID == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Group ID and Consensus ID are required")
		return
	}

	report, err := as.AnnotationService.GetConsensusReport(groupID, consensusID)
	if err != nil {
		as.handleServiceError(w, err, "fetching consensus report")
		return
	}

	response := report.ToResponse()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(response); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}

// @Summary      Delete consensus report
// @Description  Delete consensus report by ID
// @Tags         Annotation Group Consensus
// @Accept       json
// @Produce      json
// @Param        id1 path string true "Annotation Group ID"
// @Param        id2 path string true "Consensus Report ID"
// @Success      200 {object} string "Consensus report deleted successfully"
// @Failure      400 {object} string "Bad request"
// @Failure      404 {object} string "Not found"
// @Failure      500 {object} string "Internal server error"
// @Router       /annotation-groups/{id1}/consensus/{id2} [delete]
func (as *AnnotationServer) DeleteConsensusReport(w http.ResponseWriter, r *http.Request) {
	if !as.Enabled {
		as.handleJSONError(w, http.StatusNotFound, "Annotation endpoints are disabled")
		return
	}

	if r.Method != http.MethodDelete {
		as.handleJSONError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	vars := mux.Vars(r)
	groupID := vars["id1"]
	consensusID := vars["id2"]
	if groupID == "" || consensusID == "" {
		as.handleJSONError(w, http.StatusBadRequest, "Group ID and Consensus ID are required")
		return
	}

	err := as.AnnotationService.DeleteConsensusReport(groupID, consensusID)
	if err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Error deleting consensus report: %v", err))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"message": "Consensus report deleted successfully"}); err != nil {
		as.handleJSONError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to encode response: %v", err))
		return
	}
}
