"""Ops HTTP Server for Health/Metrics (v1.7.0)."""
import asyncio
from typing import Any
from aiohttp import web
from llm_monitor import CircuitBreaker, LLMUsageRepository
from db_pkg import get_session, SourceHealthRepository
from logging_setup import get_logger

logger = get_logger("ops.http")

class OpsServer:
    """Simple health check server."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/metrics", self.metrics)
        self.runner = None
        self.site = None

    async def start(self):
        """Start the server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info("ops_server_started", host=self.host, port=self.port)

    async def stop(self):
        """Stop the server."""
        if self.runner:
            await self.runner.cleanup()

    async def health_check(self, request):
        """GET /health"""
        status = "OK"
        details = {}
        
        # 1. Check Circuit Breaker
        if CircuitBreaker.is_open():
            status = "DEGRADED"
            details["circuit_breaker"] = "OPEN"
        else:
            details["circuit_breaker"] = "CLOSED"
            
        # 2. Check DB (simple query)
        try:
            from sqlalchemy import text
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
            details["db"] = "OK"
        except Exception as e:
            status = "CRITICAL"
            details["db"] = str(e)
            
        return web.json_response({
            "status": status,
            "details": details
        })

    async def metrics(self, request):
        """GET /metrics (Prometheus-like text)"""
        # Gather metrics
        async with get_session() as session:
            daily_cost = await LLMUsageRepository.get_daily_cost(session)
            recent_errors = await LLMUsageRepository.get_recent_errors(session)
            
        lines = [
            "# HELP llm_daily_cost_usd Estimated daily cost",
            "# TYPE llm_daily_cost_usd gauge",
            f"llm_daily_cost_usd {daily_cost:.4f}",
            
            "# HELP llm_errors_5m LLM errors in last 5 minutes",
            "# TYPE llm_errors_5m gauge",
            f"llm_errors_5m {recent_errors}",
            
            "# HELP circuit_breaker_status 1 if open, 0 if closed",
            "# TYPE circuit_breaker_status gauge",
            f"circuit_breaker_status {1 if CircuitBreaker.is_open() else 0}"
        ]
        
        return web.Response(text="\n".join(lines), content_type="text/plain")
