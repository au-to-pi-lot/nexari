import asyncio
import aiohttp
import pytest

from src.health_check import start_health_check_server


@pytest.mark.asyncio
async def test_health_check_server():
    # Start the health check server
    await start_health_check_server()
    
    # Give the server a moment to start
    await asyncio.sleep(1)
    
    # Test the endpoint
    async with aiohttp.ClientSession() as session:
        async with session.get('http://0.0.0.0:8080') as response:
            assert response.status == 200
            text = await response.text()
            assert text == "OK"
