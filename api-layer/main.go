// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"sync"
	"syscall"

	"github.com/cisco-eti/layer-api/pkg/common"
	"github.com/cisco-eti/layer-api/pkg/logger"
	"github.com/cisco-eti/layer-api/pkg/services/clickhouse"
	"github.com/cisco-eti/layer-api/pkg/services/http"
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

	flag.Parse()

	logger.Zap.Info("port", logger.Int("port", *port))
	logger.Zap.Info("allowOrigins", logger.String("allowOrigins", *allowOrigins))

	logger.Zap.Info("test", logger.Bool("test", *test))
	logger.Zap.Info("clickhouseUrl", logger.String("dbUrl", *clickhouseUrl))
	logger.Zap.Info("clickhouseUser", logger.String("dbUser", *clickhouseUser))
	logger.Zap.Info("clickhousePort", logger.Int("dbPort", *clickhousePort))

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

	wg.Add(1)

	httpServer := &http.HttpServer{
		AllowOrigins: *allowOrigins,
		Port:         *port,
		DataService:  clickhouseService,
		BaseUrl:      *baseUrl,
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
