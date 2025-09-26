// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package common

import "encoding/json"

type NodeStatus int

const (
	SERVER_PORT     = "SERVER_PORT"
	ALLOW_ORIGINS   = "ALLOW_ORIGINS"
	BASE_URL        = "BASE_URL"
	TEST_MODE       = "TEST_MODE"
	CLICKHOUSE_URL  = "CLICKHOUSE_URL"
	CLICKHOUSE_USER = "CLICKHOUSE_USER"
	CLICKHOUSE_DB   = "CLICKHOUSE_DB"
	CLICKHOUSE_PASS = "CLICKHOUSE_PASS"
	CLICKHOUSE_PORT = "CLICKHOUSE_PORT"
	ENV_FILE        = ".env"

	START_TIME = "start_time"
	END_TIME   = "end_time"

	SESSION_ID = "session_id"
	SPAN_ID    = "span_id"
	APP_NAME   = "app_name"

	METRIC_SCOPE_SESSION = "session"
	METRIC_SCOPE_SPAN    = "span"

	GRAPH_PARAM = "gen_ai.ioa.graph"

	NODES    = "nodes"
	ID       = "id"
	NAME     = "name"
	METADATA = "metadata"
	TYPE     = "type"

	WORKFLOW  = "workflow"
	AGENT     = "agent"
	TRANSPORT = "transport"

	EDGES = "edges"

	SOURCE = "source"
	TARGET = "target"
	DATA   = "data"

	AGENT_START_EVENT = "agent_start_event"
	AGENT_END_EVENT   = "agent_end_event"

	AGENT_START_NODE = "__start__"
	AGENT_END_NODE   = "__end__"
	AGENT_START      = "START"
	AGENT_END        = "END"
	AGENT_WORKFLOW   = "agent_workflow"

	DOT     = "."
	AUTOGEN = "autogen"

	StateRunning NodeStatus = iota
	StateDone
	StateOff
	StateNA
)

func (ns NodeStatus) String() string {
	switch ns {
	case StateRunning:
		return "running"
	case StateDone:
		return "done"
	case StateOff:
		return "off"
	case StateNA:
		return "na"
	default:
		return "unknown"
	}
}

// MarshalJSON makes NodeStatus serialize as a string in JSON
func (ns NodeStatus) MarshalJSON() ([]byte, error) {
	return json.Marshal(ns.String())
}
