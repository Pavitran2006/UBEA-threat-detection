import pytest
import httpx
import asyncio

GATEWAY_URL = "http://localhost:8000"
ANALYTICS_URL = "http://localhost:8001"
RISK_URL = "http://localhost:8002"

@pytest.mark.asyncio
async def test_gateway_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GATEWAY_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "database" in data["checks"]
        assert "elasticsearch" in data["checks"]

@pytest.mark.asyncio
async def test_analytics_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{ANALYTICS_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "elasticsearch" in data["checks"]

@pytest.mark.asyncio
async def test_risk_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{RISK_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "database" in data["checks"]
