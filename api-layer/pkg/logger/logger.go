// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package logger

import (
	"time"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// Logger is the global logger.
var Zap *zap.Logger

func init() {
	Zap = createLogger()
}

func createLogger() *zap.Logger {
	encoderCfg := zap.NewProductionEncoderConfig()
	encoderCfg.TimeKey = "timestamp"
	encoderCfg.EncodeTime = zapcore.ISO8601TimeEncoder

	config := zap.Config{
		Level:             zap.NewAtomicLevelAt(zap.InfoLevel),
		Development:       false,
		DisableCaller:     false,
		DisableStacktrace: false,
		Sampling:          nil,
		Encoding:          "json",
		EncoderConfig:     encoderCfg,
		OutputPaths: []string{
			"stderr",
		},
		ErrorOutputPaths: []string{
			"stderr",
		},
	}

	return zap.Must(config.Build())
}

func Error(err error) zap.Field {
	return zap.Error(err)
}

func String(key string, value string) zap.Field {
	return zap.String(key, value)
}

func Strings(key string, values []string) zap.Field {
	return zap.Strings(key, values)
}

func Int(key string, value int) zap.Field {
	return zap.Int(key, value)
}

func Int32(key string, value int32) zap.Field {
	return zap.Int32(key, value)
}

func Int64(key string, value int64) zap.Field {
	return zap.Int64(key, value)
}

func Bool(key string, value bool) zap.Field {
	return zap.Bool(key, value)
}

func Duration(key string, value time.Duration) zap.Field {
	return zap.Duration(key, value)
}

func Any(key string, value interface{}) zap.Field {
	return zap.Any(key, value)
}
