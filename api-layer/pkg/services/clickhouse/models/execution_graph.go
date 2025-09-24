package models

type Node struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Status string `json:"status"`
	Type   string `json:"type"`
}

type Edge struct {
	From            string `json:"from"`
	To              string `json:"to"`
	ExecutionNumber int    `json:"execution_number"`
}

type ExecutionGraph struct {
	SessionID string `json:"session_id"`
	Nodes     []Node `json:"nodes"`
	Edges     []Edge `json:"edges"`
	Timestamp string `json:"timestamp"`
}