// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package models

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

// JSONRawMessage is a custom type that handles ClickHouse JSON storage/retrieval
type JSONRawMessage json.RawMessage

// Scan implements the sql.Scanner interface for reading from database
func (j *JSONRawMessage) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}

	switch v := value.(type) {
	case string:
		*j = JSONRawMessage(v)
		return nil
	case []byte:
		*j = JSONRawMessage(v)
		return nil
	default:
		return fmt.Errorf("cannot scan %T into JSONRawMessage", value)
	}
}

// Value implements the driver.Valuer interface for writing to database
func (j JSONRawMessage) Value() (driver.Value, error) {
	if j == nil {
		return nil, nil
	}
	return string(j), nil
}

// MarshalJSON implements json.Marshaler
func (j JSONRawMessage) MarshalJSON() ([]byte, error) {
	if j == nil {
		return []byte("null"), nil
	}
	return []byte(j), nil
}

// UnmarshalJSON implements json.Unmarshaler
func (j *JSONRawMessage) UnmarshalJSON(data []byte) error {
	*j = JSONRawMessage(data)
	return nil
}

// OtelTraces represents an Otel tracing span in ClickHouse
type Metric struct {
	ID        *string         `json:"id" gorm:"column:ID;type:String;primaryKey;not null"`
	SpanId    *string         `json:"span_id" gorm:"column:SpanId;type:String;not null"`
	TraceId   *string         `json:"trace_id" gorm:"column:TraceId;type:String;not null"`
	SessionId *string         `json:"session_id" gorm:"column:SessionId;type:String;not null"`
	TimeStamp *time.Time      `json:"timestamp" gorm:"column:Timestamp;type:DateTime64(9);not null"`
	Metrics   *JSONRawMessage `json:"metrics" gorm:"column:Metrics;type:String;not null" swaggertype:"string" example:"{\"accuracy\":\"0.95\",\"latency_ms\":\"120\"}"` // Use json.RawMessage to store arbitrary JSON data
	AppName   *string         `json:"app_name" gorm:"column:AppName;type:String;not null"`
	AppId     *string         `json:"app_id" gorm:"column:AppId;type:String;not null"`
	Scope     *string         `json:"-" gorm:"column:Scope;type:String;not null"`
}

// MetricCreateRequest represents the request payload for creating a metric (without ID and timestamp)
type MetricCreateRequest struct {
	SpanId    *string         `json:"span_id" binding:"required"`
	TraceId   *string         `json:"trace_id" binding:"required"`
	SessionId *string         `json:"session_id" binding:"required"`
	Metrics   *JSONRawMessage `json:"metrics" binding:"required" swaggertype:"string" example:"{\"key\":\"value\"}"` // Use json.RawMessage to store arbitrary JSON data
	AppName   *string         `json:"app_name" binding:"required"`
	AppId     *string         `json:"app_id" binding:"required"`
}

// MetricResponse represents the response payload when retrieving metrics (with all fields)
type MetricResponse struct {
	ID        *string         `json:"id"`
	SpanId    *string         `json:"span_id"`
	TraceId   *string         `json:"trace_id"`
	SessionId *string         `json:"session_id"`
	TimeStamp *time.Time      `json:"timestamp"`
	Metrics   *JSONRawMessage `json:"metrics" swaggertype:"string" example:"{\"accuracy\":\"0.95\",\"latency_ms\":\"120\"}"` // Use json.RawMessage to store arbitrary JSON data
	AppName   *string         `json:"app_name"`
	AppId     *string         `json:"app_id"`
}

// ToMetric converts a MetricCreateRequest to a Metric
func (req *MetricCreateRequest) ToMetric() *Metric {
	scope := "session" // Default scope, you can modify this as needed
	return &Metric{
		SpanId:    req.SpanId,
		TraceId:   req.TraceId,
		SessionId: req.SessionId,
		Metrics:   req.Metrics,
		AppName:   req.AppName,
		AppId:     req.AppId,
		Scope:     &scope,
	}
}

// ToMetricWithScope converts a MetricCreateRequest to a Metric with specified scope
func (req *MetricCreateRequest) ToMetricWithScope(scope string) *Metric {
	return &Metric{
		SpanId:    req.SpanId,
		TraceId:   req.TraceId,
		SessionId: req.SessionId,
		Metrics:   req.Metrics,
		AppName:   req.AppName,
		AppId:     req.AppId,
		Scope:     &scope,
	}
}

// ToResponse converts a Metric to a MetricResponse
func (m *Metric) ToResponse() *MetricResponse {
	return &MetricResponse{
		ID:        m.ID,
		SpanId:    m.SpanId,
		TraceId:   m.TraceId,
		SessionId: m.SessionId,
		TimeStamp: m.TimeStamp,
		Metrics:   m.Metrics,
		AppName:   m.AppName,
		AppId:     m.AppId,
	}
}

// BeforeCreate hook to generate UUID before creating record
func (m *Metric) BeforeCreate(tx *gorm.DB) error {
	id := uuid.New().String()
	m.ID = &id

	now := time.Now()
	m.TimeStamp = &now

	// Check if all required fields are present (not empty/nil)
	if m.isEmptyReflection() {
		return errors.New("cannot create Metric: required fields are empty")
	}

	return nil
}

// isEmptyReflection checks if critical fields are empty/nil
func (m *Metric) isEmptyReflection() bool {
	// Check critical required fields
	if m.SpanId == nil || *m.SpanId == "" {
		return true
	}
	if m.TraceId == nil || *m.TraceId == "" {
		return true
	}
	if m.SessionId == nil || *m.SessionId == "" {
		return true
	}
	if m.AppName == nil || *m.AppName == "" {
		return true
	}
	if m.AppId == nil || *m.AppId == "" {
		return true
	}
	if m.Metrics == nil || len(*m.Metrics) == 0 {
		return true
	}
	if m.Scope == nil || *m.Scope == "" {
		return true
	}

	return false // All required fields are present
}

// TableName overrides the table name in GORM
func (Metric) TableName() string {
	return "derived_metrics"
}
