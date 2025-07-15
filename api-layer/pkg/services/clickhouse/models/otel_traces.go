// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package models

import "time"

// OtelTraces represents an Otel tracing span in ClickHouse
type OtelTraces struct {
	Timestamp          time.Time           `gorm:"column:Timestamp;type:DateTime64(9)"`
	TraceId            string              `gorm:"column:TraceId;type:String"`
	SpanId             string              `gorm:"column:SpanId;type:String"`
	ParentSpanId       string              `gorm:"column:ParentSpanId;type:String"`
	TraceState         string              `gorm:"column:TraceState;type:String"`
	SpanName           string              `gorm:"column:SpanName;type:LowCardinality(String)"`
	SpanKind           string              `gorm:"column:SpanKind;type:LowCardinality(String)"`
	ServiceName        string              `gorm:"column:ServiceName;type:LowCardinality(String)"`
	ResourceAttributes map[string]string   `gorm:"column:ResourceAttributes;type:Map(LowCardinality(String), String)"`
	ScopeName          string              `gorm:"column:ScopeName;type:String"`
	ScopeVersion       string              `gorm:"column:ScopeVersion;type:String"`
	SpanAttributes     map[string]string   `gorm:"column:SpanAttributes;type:Map(LowCardinality(String), String)"`
	Duration           uint64              `gorm:"column:Duration;type:UInt64"`
	StatusCode         string              `gorm:"column:StatusCode;type:LowCardinality(String)"`
	StatusMessage      string              `gorm:"column:StatusMessage;type:String"`
	EventsTimestamp    []time.Time         `gorm:"column:Events.Timestamp;type:Array(DateTime64(9))"`
	EventsName         []string            `gorm:"column:Events.Name;type:Array(LowCardinality(String))"`
	EventsAttributes   []map[string]string `gorm:"column:Events.Attributes;type:Array(Map(LowCardinality(String), String))"`
	LinksTraceId       []string            `gorm:"column:Links.TraceId;type:Array(String)"`
	LinksSpanId        []string            `gorm:"column:Links.SpanId;type:Array(String)"`
	LinksTraceState    []string            `gorm:"column:Links.TraceState;type:Array(String)"`
	LinksAttributes    []map[string]string `gorm:"column:Links.Attributes;type:Array(Map(LowCardinality(String), String))"`
}

// TableName overrides the table name in GORM
func (OtelTraces) TableName() string {
	return "otel_traces"
}
