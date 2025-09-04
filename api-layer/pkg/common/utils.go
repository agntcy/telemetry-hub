// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package common

import (
	"errors"
	"math/rand"
	"os"
	"strconv"

	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/joho/godotenv"
)

func RandomInt(min, max int) int {
	return rand.Intn(max-min) + min
}

func GetEnvString(key string, fallback string) string {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}
	return value
}

func GetEnvInt(key string, fallback int) int {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}
	intValue, err := strconv.Atoi(value)
	if err != nil {
		logger.Zap.Error("Error converting env var to int", logger.Error(err), logger.String("key", key), logger.String("value", value))
		return fallback
	}
	return intValue
}

func GetEnvBool(key string, fallback bool) bool {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}
	boolValue, err := strconv.ParseBool(value)
	if err != nil {
		logger.Zap.Error("Error converting env var to bool", logger.Error(err), logger.String("key", key), logger.String("value", value))
		return fallback
	}
	return boolValue
}

func LoadEnv() {
	// Check if the .env file exists
	if _, err := os.Stat(ENV_FILE); err == nil {
		// Load the .env file
		err = godotenv.Load(ENV_FILE)
		if err != nil {
			logger.Zap.Error("Error loading .env file", logger.Error(err))
		}
	} else {
		logger.Zap.Info("No .env file found, using environment variables")
	}
}

func ParseTime(timeString string) (timeParsed time.Time, err error) {
	if timeString == "" {
		logger.Zap.Error("Date cannot be empty")
		return timeParsed, errors.New("date cannot be empty")
	}

	timeParsed, err = time.Parse(time.RFC3339, timeString)
	// Check ISO 8601 UTC format
	if err != nil || timeParsed.Location() != time.UTC {
		logger.Zap.Error("Invalid date format, must be in ISO 8601 UTC format", logger.Error(err), logger.String("time", timeString))
		return timeParsed, errors.New("invalid date format, must be in ISO 8601 UTC format")
	}

	return timeParsed, nil
}
