// Package docs Code generated by swaggo/swag. DO NOT EDIT
package docs

import "github.com/swaggo/swag"

const docTemplate = `{
    "schemes": {{ marshal .Schemes }},
    "swagger": "2.0",
    "info": {
        "description": "{{escape .Description}}",
        "title": "{{.Title}}",
        "contact": {},
        "version": "{{.Version}}"
    },
    "host": "{{.Host}}",
    "basePath": "{{.BasePath}}",
    "paths": {
        "/metrics/session": {
            "post": {
                "description": "Write session metrics to the server",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Write session metrics",
                "parameters": [
                    {
                        "description": "Metric to write",
                        "name": "metric",
                        "in": "body",
                        "required": true,
                        "schema": {
                            "$ref": "#/definitions/http.CreateMetric"
                        }
                    }
                ],
                "responses": {
                    "201": {
                        "description": "Metric created successfully",
                        "schema": {
                            "$ref": "#/definitions/http.Metric"
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "/metrics/session/{session_id}": {
            "get": {
                "description": "Get metrics by session ID",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Get metrics by session ID",
                "parameters": [
                    {
                        "type": "string",
                        "example": "\"session_abc123\"",
                        "description": "Session ID",
                        "name": "session_id",
                        "in": "path",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of metrics for the session\" example([{\"id\": \"metric_001\", \"span_id\": \"span_abc123\", \"trace_id\": \"trace_def456\", \"session_id\": \"session_abc123\", \"timestamp\": \"2023-06-25T15:30:00Z\", \"metrics\": {\"accuracy\": \"0.95\", \"latency_ms\": \"120\"}, \"app_name\": \"ml-service\", \"app_id\": \"app-001\"}])",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/http.Metric"
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "/metrics/span": {
            "post": {
                "description": "Write span metrics to the server",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Write span metrics",
                "parameters": [
                    {
                        "description": "Metric to write",
                        "name": "metric",
                        "in": "body",
                        "required": true,
                        "schema": {
                            "$ref": "#/definitions/http.CreateMetric"
                        }
                    }
                ],
                "responses": {
                    "201": {
                        "description": "Metric created successfully",
                        "schema": {
                            "$ref": "#/definitions/http.Metric"
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "/metrics/span/{span_id}": {
            "get": {
                "description": "Get metrics by span ID",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Get metrics by span ID",
                "parameters": [
                    {
                        "type": "string",
                        "example": "\"span\"",
                        "description": "Span ID",
                        "name": "span_id",
                        "in": "path",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of metrics for the span\" example([{\"id\": \"metric_001\", \"span_id\": \"span_abc123\", \"trace_id\": \"trace_def456\", \"session_id\": \"session_abc123\", \"timestamp\": \"2023-06-25T15:30:00Z\", \"metrics\": {\"accuracy\": \"0.95\", \"latency_ms\": \"120\"}, \"app_name\": \"ml-service\", \"app_id\": \"app-001\"}])",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/http.Metric"
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "/traces/session/{session_id}": {
            "get": {
                "description": "Get traces by session ID",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Get traces by session ID",
                "parameters": [
                    {
                        "type": "string",
                        "example": "\"session_abc123\"",
                        "description": "Session ID",
                        "name": "session_id",
                        "in": "path",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of traces for the session\" example([{\"trace_id\": \"trace_def456\", \"span_name\": \"ml_inference\", \"timestamp\": \"2023-06-25T15:30:00Z\"}, {\"trace_id\": \"trace_ghi789\", \"span_name\": \"data_processing\", \"timestamp\": \"2023-06-25T15:31:00Z\"}])",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/http.Trace"
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "/traces/sessions": {
            "get": {
                "description": "Get sessions by start and end time",
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "tags": [
                    "APIs"
                ],
                "summary": "Get sessions",
                "parameters": [
                    {
                        "type": "string",
                        "example": "\"2023-06-25T15:04:05Z\"",
                        "description": "Start time in ISO 8601 UTC format (e.g. 2023-06-25T15:04:05Z)",
                        "name": "start_time",
                        "in": "query",
                        "required": true
                    },
                    {
                        "type": "string",
                        "example": "\"2023-06-25T18:04:05Z\"",
                        "description": "End time in ISO 8601 UTC format (e.g. 2023-06-25T15:04:05Z)",
                        "name": "end_time",
                        "in": "query",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of session IDs with minimum timestamps\" example([{\"id\": \"session_abc123\", \"start_timestamp\": \"2023-06-25T15:30:00Z\"}, {\"id\": \"session_def456\", \"start_timestamp\": \"2023-06-25T16:15:00Z\"}])",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/http.SessionID"
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    },
    "definitions": {
        "http.CreateMetric": {
            "type": "object",
            "required": [
                "app_id",
                "app_name",
                "metrics",
                "session_id",
                "span_id",
                "trace_id"
            ],
            "properties": {
                "app_id": {
                    "type": "string"
                },
                "app_name": {
                    "type": "string"
                },
                "metrics": {
                    "description": "Use json.RawMessage to store arbitrary JSON data",
                    "type": "string",
                    "example": "{\"key\":\"value\"}"
                },
                "session_id": {
                    "type": "string"
                },
                "span_id": {
                    "type": "string"
                },
                "trace_id": {
                    "type": "string"
                }
            }
        },
        "http.Metric": {
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string"
                },
                "app_name": {
                    "type": "string"
                },
                "id": {
                    "type": "string"
                },
                "metrics": {
                    "description": "Use json.RawMessage to store arbitrary JSON data",
                    "type": "string",
                    "example": "{\"accuracy\":\"0.95\",\"latency_ms\":\"120\"}"
                },
                "session_id": {
                    "type": "string"
                },
                "span_id": {
                    "type": "string"
                },
                "timestamp": {
                    "type": "string"
                },
                "trace_id": {
                    "type": "string"
                }
            }
        },
        "http.SessionID": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string"
                },
                "start_timestamp": {
                    "type": "string"
                }
            }
        },
        "http.Trace": {
            "type": "object",
            "properties": {
                "duration": {
                    "type": "integer"
                },
                "eventsAttributes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "string"
                        }
                    }
                },
                "eventsName": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "eventsTimestamp": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "linksAttributes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "string"
                        }
                    }
                },
                "linksSpanId": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "linksTraceId": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "linksTraceState": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "parentSpanId": {
                    "type": "string"
                },
                "resourceAttributes": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string"
                    }
                },
                "scopeName": {
                    "type": "string"
                },
                "scopeVersion": {
                    "type": "string"
                },
                "serviceName": {
                    "type": "string"
                },
                "spanAttributes": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string"
                    }
                },
                "spanId": {
                    "type": "string"
                },
                "spanKind": {
                    "type": "string"
                },
                "spanName": {
                    "type": "string"
                },
                "statusCode": {
                    "type": "string"
                },
                "statusMessage": {
                    "type": "string"
                },
                "timestamp": {
                    "type": "string"
                },
                "traceId": {
                    "type": "string"
                },
                "traceState": {
                    "type": "string"
                }
            }
        }
    }
}`

// SwaggerInfo holds exported Swagger Info so clients can modify it
var SwaggerInfo = &swag.Spec{
	Version:          "",
	Host:             "",
	BasePath:         "",
	Schemes:          []string{},
	Title:            "",
	Description:      "",
	InfoInstanceName: "swagger",
	SwaggerTemplate:  docTemplate,
	LeftDelim:        "{{",
	RightDelim:       "}}",
}

func init() {
	swag.Register(SwaggerInfo.InstanceName(), SwaggerInfo)
}
