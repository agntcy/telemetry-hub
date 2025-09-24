// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package models

import "fmt"

// ServiceError represents different types of service errors
type ServiceError struct {
	Type    ServiceErrorType
	Message string
	Err     error
}

// ServiceErrorType represents the type of service error
type ServiceErrorType int

const (
	// ErrorTypeNotFound indicates the requested resource was not found
	ErrorTypeNotFound ServiceErrorType = iota
	// ErrorTypeValidation indicates a validation error
	ErrorTypeValidation
	// ErrorTypeConflict indicates a conflict error (e.g., duplicate key)
	ErrorTypeConflict
	// ErrorTypeInternal indicates an internal server error
	ErrorTypeInternal
)

// Error implements the error interface
func (se *ServiceError) Error() string {
	if se.Err != nil {
		return fmt.Sprintf("%s: %v", se.Message, se.Err)
	}
	return se.Message
}

// IsNotFound checks if the error is a not found error
func (se *ServiceError) IsNotFound() bool {
	return se.Type == ErrorTypeNotFound
}

// IsValidation checks if the error is a validation error
func (se *ServiceError) IsValidation() bool {
	return se.Type == ErrorTypeValidation
}

// IsConflict checks if the error is a conflict error
func (se *ServiceError) IsConflict() bool {
	return se.Type == ErrorTypeConflict
}

// IsInternal checks if the error is an internal error
func (se *ServiceError) IsInternal() bool {
	return se.Type == ErrorTypeInternal
}

// NewNotFoundError creates a new not found error
func NewNotFoundError(message string) *ServiceError {
	return &ServiceError{
		Type:    ErrorTypeNotFound,
		Message: message,
	}
}

// NewValidationError creates a new validation error
func NewValidationError(message string) *ServiceError {
	return &ServiceError{
		Type:    ErrorTypeValidation,
		Message: message,
	}
}

// NewConflictError creates a new conflict error
func NewConflictError(message string) *ServiceError {
	return &ServiceError{
		Type:    ErrorTypeConflict,
		Message: message,
	}
}

// NewInternalError creates a new internal error
func NewInternalError(message string, err error) *ServiceError {
	return &ServiceError{
		Type:    ErrorTypeInternal,
		Message: message,
		Err:     err,
	}
}

// IsServiceError checks if an error is a ServiceError and returns it
func IsServiceError(err error) (*ServiceError, bool) {
	if serviceErr, ok := err.(*ServiceError); ok {
		return serviceErr, true
	}
	return nil, false
}