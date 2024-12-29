import pytest

from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_pypi_simple_index():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/pypi/simple")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_pypi_package_info():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/pypi/requests/info")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "versions" in data
