// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

// @title API-Layer API
// @version 1.0
// @description This service is a part of the API-Layer project. It helps to understand if the service is alive and running.
// @host localhost:8080
// @schemes http
// @BasePath /
package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/agntcy/telemetry-hub/api-layer/pkg/common"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/logger"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/clickhouse"
	"github.com/agntcy/telemetry-hub/api-layer/pkg/services/http"
	services "github.com/agntcy/telemetry-hub/api-layer/pkg/services/interfaces"
)

func main() {

	common.LoadEnv()

	// Server input
	port := flag.Int("port", common.GetEnvInt(common.SERVER_PORT, 8080), "Port to run the server on")
	allowOrigins := flag.String("allowOrigins", common.GetEnvString(common.ALLOW_ORIGINS, "http://localhost:3000,http://localhost:8080"), "Allowed Origins")
	baseUrl := flag.String("baseUrl", common.GetEnvString(common.BASE_URL, "localhost:8080"), "Base URL for the API")
	// Start as test
	test := flag.Bool("test", common.GetEnvBool("TEST_MODE", false), "Start as test")

	clickhouseUrl := flag.String("clickhouseUrl", common.GetEnvString(common.CLICKHOUSE_URL, "localhost"), "Clickhouse Url")
	clickhouseUser := flag.String("clickhouseUser", common.GetEnvString(common.CLICKHOUSE_USER, "default"), "Clickhouse User")
	clickhouseDB := flag.String("clickhouseDB", common.GetEnvString(common.CLICKHOUSE_DB, "default"), "Clickhouse DB")
	clickhousePass := flag.String("clickhousePass", common.GetEnvString(common.CLICKHOUSE_PASS, "password"), "Clickhouse Password")
	clickhousePort := flag.Int("clickhousePort", common.GetEnvInt(common.CLICKHOUSE_PORT, 9000), "Clickhouse Port")

	// Metrics-specific ClickHouse parameters
	metricsClickhouseUrl := flag.String("metricsClickhouseUrl", common.GetEnvString("METRICS_CLICKHOUSE_URL", ""), "Metrics Clickhouse Url (defaults to main clickhouse if not set)")
	metricsClickhouseUser := flag.String("metricsClickhouseUser", common.GetEnvString("METRICS_CLICKHOUSE_USER", ""), "Metrics Clickhouse User (defaults to main clickhouse if not set)")
	metricsClickhouseDB := flag.String("metricsClickhouseDB", common.GetEnvString("METRICS_CLICKHOUSE_DB", ""), "Metrics Clickhouse DB (defaults to main clickhouse if not set)")
	metricsClickhousePass := flag.String("metricsClickhousePass", common.GetEnvString("METRICS_CLICKHOUSE_PASS", ""), "Metrics Clickhouse Password (defaults to main clickhouse if not set)")
	metricsClickhousePort := flag.Int("metricsClickhousePort", common.GetEnvInt("METRICS_CLICKHOUSE_PORT", 0), "Metrics Clickhouse Port (defaults to main clickhouse if not set)")

	// Annotation parameters
	annotationEnabled := flag.Bool("annotation", common.GetEnvBool("ANNOTATION_ENABLED", false), "Enable annotation endpoints")
	annotationClickhouseUrl := flag.String("annotationClickhouseUrl", common.GetEnvString("ANNOTATION_CLICKHOUSE_URL", ""), "Annotation Clickhouse Url (defaults to main clickhouse if not set)")
	annotationClickhouseDB := flag.String("annotationClickhouseDB", common.GetEnvString("ANNOTATION_CLICKHOUSE_DB", ""), "Annotation Clickhouse DB (defaults to main clickhouse if not set)")
	annotationClickhousePort := flag.Int("annotationClickhousePort", common.GetEnvInt("ANNOTATION_CLICKHOUSE_PORT", 0), "Annotation Clickhouse Port (defaults to main clickhouse if not set)")
	annotationClickhouseUser := flag.String("annotationClickhouseUser", common.GetEnvString("ANNOTATION_CLICKHOUSE_USER", ""), "Annotation Clickhouse User (defaults to main clickhouse if not set)")
	annotationClickhousePass := flag.String("annotationClickhousePass", common.GetEnvString("ANNOTATION_CLICKHOUSE_PASS", ""), "Annotation Clickhouse Password (defaults to main clickhouse if not set)")

	// MCE (Metrics Computation Engine) parameters
	mceEnabled := flag.Bool("mce", common.GetEnvBool("MCE_ENABLED", false), "Enable MCE (Metrics Computation Engine) endpoints")
	mceHost := flag.String("mceHost", common.GetEnvString("MCE_HOST", "localhost"), "MCE server host")
	mcePort := flag.Int("mcePort", common.GetEnvInt("MCE_PORT", 8000), "MCE server port")
	mceBaseURL := flag.String("mceBaseURL", common.GetEnvString("MCE_BASE_URL", ""), "MCE server base URL path")
	mceTimeout := flag.Int("mceTimeout", common.GetEnvInt("MCE_TIMEOUT", 30), "MCE server timeout in seconds")

	flag.Parse()

	logger.Zap.Info("port", logger.Int("port", *port))
	logger.Zap.Info("allowOrigins", logger.String("allowOrigins", *allowOrigins))

	logger.Zap.Info("test", logger.Bool("test", *test))
	logger.Zap.Info("clickhouseUrl", logger.String("dbUrl", *clickhouseUrl))
	logger.Zap.Info("clickhouseUser", logger.String("dbUser", *clickhouseUser))
	logger.Zap.Info("clickhousePort", logger.Int("dbPort", *clickhousePort))

	logger.Zap.Info("metricsClickhouseUrl", logger.String("metricsDbUrl", *metricsClickhouseUrl))
	if *metricsClickhouseUrl != "" {
		logger.Zap.Info("metricsClickhouseDB", logger.String("metricsDbName", *metricsClickhouseDB))
		logger.Zap.Info("metricsClickhousePort", logger.Int("metricsDbPort", *metricsClickhousePort))
		logger.Zap.Info("metricsClickhouseUser", logger.String("metricsDbUser", *metricsClickhouseUser))
	}

	logger.Zap.Info("annotationEnabled", logger.Bool("annotationEnabled", *annotationEnabled))
	if *annotationEnabled {
		logger.Zap.Info("annotationClickhouseUrl", logger.String("annotationDbUrl", *annotationClickhouseUrl))
		logger.Zap.Info("annotationClickhouseDB", logger.String("annotationDbName", *annotationClickhouseDB))
		logger.Zap.Info("annotationClickhousePort", logger.Int("annotationDbPort", *annotationClickhousePort))
		logger.Zap.Info("annotationClickhouseUser", logger.String("annotationDbUser", *annotationClickhouseUser))
	}

	logger.Zap.Info("mceEnabled", logger.Bool("mceEnabled", *mceEnabled))
	if *mceEnabled {
		logger.Zap.Info("mceHost", logger.String("mceHost", *mceHost))
		logger.Zap.Info("mcePort", logger.Int("mcePort", *mcePort))
		logger.Zap.Info("mceBaseURL", logger.String("mceBaseURL", *mceBaseURL))
		logger.Zap.Info("mceTimeout", logger.Int("mceTimeout", *mceTimeout))
	}

	var wg sync.WaitGroup
	logger.Zap.Info("Starting server")
	sgl := make(chan os.Signal)

	ctx, cancel := context.WithCancel(context.Background())

	clickhouseService := &clickhouse.ClickhouseService{
		Url:  *clickhouseUrl,
		User: *clickhouseUser,
		Pass: *clickhousePass,
		Port: *clickhousePort,
		DB:   *clickhouseDB,
	}

	if !*test {
		clickhouseService.Init()
	}

	// Create metrics service with dedicated ClickHouse settings if provided
	var metricsService services.MetricsService
	if *metricsClickhouseUrl != "" {
		// Use dedicated metrics ClickHouse settings
		metricsDbUrl := *metricsClickhouseUrl
		metricsDbUser := *metricsClickhouseUser
		if metricsDbUser == "" {
			metricsDbUser = *clickhouseUser
		}

		metricsDbPass := *metricsClickhousePass
		if metricsDbPass == "" {
			metricsDbPass = *clickhousePass
		}

		metricsDbName := *metricsClickhouseDB
		if metricsDbName == "" {
			metricsDbName = *clickhouseDB
		}

		metricsDbPort := *metricsClickhousePort
		if metricsDbPort == 0 {
			metricsDbPort = *clickhousePort
		}

		metricsClickhouseService := &clickhouse.ClickhouseService{
			Url:  metricsDbUrl,
			User: metricsDbUser,
			Pass: metricsDbPass,
			Port: metricsDbPort,
			DB:   metricsDbName,
		}

		if !*test {
			metricsClickhouseService.Init()
		}
		metricsService = metricsClickhouseService
		logger.Zap.Info("Using dedicated metrics ClickHouse service")
	} else {
		// Use the same ClickHouse service for both traces and metrics
		metricsService = clickhouseService
		logger.Zap.Info("Using shared ClickHouse service for traces and metrics")
	}

	// Create annotation service if enabled
	var annotationService services.AnnotationService
	if *annotationEnabled {
		// Set defaults for annotation ClickHouse settings if not provided
		annotationUrl := *annotationClickhouseUrl
		if annotationUrl == "" {
			annotationUrl = *clickhouseUrl
		}

		annotationDB := *annotationClickhouseDB
		if annotationDB == "" {
			annotationDB = *clickhouseDB
		}

		annotationPort := *annotationClickhousePort
		if annotationPort == 0 {
			annotationPort = *clickhousePort
		}

		annotationUser := *annotationClickhouseUser
		if annotationUser == "" {
			annotationUser = *clickhouseUser
		}

		annotationPass := *annotationClickhousePass
		if annotationPass == "" {
			annotationPass = *clickhousePass
		}

		if *test {
			// Use mock service for testing
			annotationService = clickhouse.NewMockAnnotationService()
		} else {
			// Use real ClickHouse annotation service in production
			var err error
			annotationService, err = clickhouse.NewClickhouseAnnotationService(
				annotationUrl,
				annotationUser,
				annotationPass,
				annotationDB,
				annotationPort,
			)

			if err != nil {
				logger.Zap.Error("Failed to create ClickHouse annotation service", logger.Error(err))
				logger.Zap.Info("Falling back to mock annotation service for this session")
				annotationService = clickhouse.NewMockAnnotationService()
			} else {
				logger.Zap.Info("ClickHouse annotation service initialized successfully")
			}
		}
	}

	// Create MCE server if enabled
	var mceServer *http.MCEServer
	if *mceEnabled {
		mceConfig := http.MCEConfig{
			Host:    *mceHost,
			Port:    *mcePort,
			BaseURL: *mceBaseURL,
			Timeout: time.Duration(*mceTimeout) * time.Second,
		}
		mceServer = http.NewMCEServer(true, mceConfig)
		logger.Zap.Info("MCE server initialized successfully")
	}

	wg.Add(1)

	httpServer := &http.HttpServer{
		AllowOrigins:      *allowOrigins,
		Port:              *port,
		DataService:       clickhouseService,
		MetricsService:    metricsService,
		AnnotationService: annotationService,
		MCEServer:         mceServer,
		BaseUrl:           *baseUrl,
		AnnotationEnabled: *annotationEnabled,
	}
	go func() {

		httpServer.SignalsChannel = sgl
		httpServer.Run(ctx, &wg)
		logger.Zap.Info("Exit Http server")

	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, os.Interrupt)

	sig := <-sigChan
	logger.Zap.Info("Received signal", logger.String("signal", sig.String()))

	cancel()
	logger.Zap.Info("Waiting for server to stop")
	wg.Wait()

	logger.Zap.Info("Server stopped")
}
