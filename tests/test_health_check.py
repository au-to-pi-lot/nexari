import asyncio
import aiohttp
import pytest
from unittest.mock import Mock

from src.health_check import start_health_check_server


@pytest.mark.asyncio
async def test_health_check_server():
    # Create a mock Discord client
    mock_client = Mock()
    mock_client.is_ready.return_value = True
    
    # Start the health check server with mock client
    await start_health_check_server(mock_client)
    
    # Give the server a moment to start
    await asyncio.sleep(1)
    
    # Test both endpoints
    async with aiohttp.ClientSession() as session:
        # Test liveness endpoint
        async with session.get('http://0.0.0.0:8080/healthz') as response:
            assert response.status == 200
            text = await response.text()
            assert text == "OK"
            
        # Test readiness endpoint
        async with session.get('http://0.0.0.0:8080/readyz') as response:
            assert response.status == 200
            text = await response.text()
            assert text == "OK"
            
        # Test readiness when Discord is not ready
        mock_client.is_ready.return_value = False
        async with session.get('http://0.0.0.0:8080/readyz') as response:
            assert response.status == 503
            text = await response.text()
            assert text == "Discord connection not ready"
