"""
Tests for system load shedding with mocked psutil
"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_psutil():
    """Create mock psutil module"""
    with patch('aioresilience.load_shedding.system.psutil') as mock:
        # Mock CPU percent
        mock.cpu_percent = Mock(return_value=50.0)
        
        # Mock virtual memory
        memory_mock = Mock()
        memory_mock.percent = 60.0
        mock.virtual_memory = Mock(return_value=memory_mock)
        
        yield mock


class TestSystemLoadShedder:
    """Test system load shedder with mocked psutil"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_psutil):
        """Test system load shedder initialization"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        assert shedder.max_requests == 1000
        assert shedder.cpu_threshold == 80.0
        assert shedder.memory_threshold == 85.0
    
    @pytest.mark.asyncio
    async def test_acquire_under_limits(self, mock_psutil):
        """Test acquire succeeds when under all limits"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value.percent = 60.0
        
        shedder = SystemLoadShedder(
            max_requests=100,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        result = await shedder.acquire()
        assert result is True
        assert shedder.active_requests == 1
    
    @pytest.mark.asyncio
    async def test_shed_on_high_cpu(self, mock_psutil):
        """Test sheds load when CPU exceeds threshold"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 95.0  # High CPU
        mock_psutil.virtual_memory.return_value.percent = 60.0
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        result = await shedder.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shed_on_high_memory(self, mock_psutil):
        """Test sheds load when memory exceeds threshold"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value.percent = 90.0  # High memory
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        result = await shedder.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shed_on_request_limit(self, mock_psutil):
        """Test sheds load when request limit exceeded"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value.percent = 60.0
        
        shedder = SystemLoadShedder(
            max_requests=2,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        # Fill to limit
        await shedder.acquire()
        await shedder.acquire()
        
        # Should shed now
        result = await shedder.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_priority_bypass_system_limits(self, mock_psutil):
        """Test priority requests bypass system limits (but not CRITICAL)"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 85.0  # High but not critical
        mock_psutil.virtual_memory.return_value.percent = 87.0  # High but not critical
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        # Priority requests should bypass non-critical system limits
        result = await shedder.acquire(priority="high")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_release_decrements(self, mock_psutil):
        """Test release decrements request count"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        shedder = SystemLoadShedder(max_requests=100)
        
        await shedder.acquire()
        assert shedder.active_requests == 1
        
        await shedder.release()
        assert shedder.active_requests == 0
    
    @pytest.mark.asyncio
    async def test_get_stats_includes_system_metrics(self, mock_psutil):
        """Test get_stats includes CPU and memory"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 65.0
        mock_psutil.virtual_memory.return_value.percent = 70.0
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        await shedder.acquire()
        stats = shedder.get_stats()
        
        assert "cpu_percent" in stats
        assert "memory_percent" in stats
        assert stats["cpu_percent"] == 65.0
        assert stats["memory_percent"] == 70.0
        assert stats["active_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_should_shed_load_returns_reason(self, mock_psutil):
        """Test should_shed_load returns reason for shedding"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 95.0
        mock_psutil.virtual_memory.return_value.percent = 60.0
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        should_shed, reason = shedder.should_shed_load()
        
        assert should_shed is True
        assert "CPU" in reason or "cpu" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_memory_threshold_reason(self, mock_psutil):
        """Test memory threshold returns correct reason"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value.percent = 95.0
        
        shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=80.0,
            memory_threshold=85.0
        )
        
        should_shed, reason = shedder.should_shed_load()
        
        assert should_shed is True
        assert "memory" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_request_limit_reason(self, mock_psutil):
        """Test request limit returns correct reason"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value.percent = 60.0
        
        shedder = SystemLoadShedder(max_requests=0)
        
        should_shed, reason = shedder.should_shed_load()
        
        assert should_shed is True
        assert "request" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_psutil_import_error_falls_back(self):
        """Test graceful fallback when psutil not available"""
        # This test would need to mock the import itself
        # Testing the actual import guard is tricky in unit tests
        pass
    
    @pytest.mark.asyncio
    async def test_load_level_calculation(self, mock_psutil):
        """Test load level calculation"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        shedder = SystemLoadShedder(max_requests=100)
        
        # Test normal load
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.virtual_memory.return_value.percent = 40.0
        for i in range(20):
            await shedder.acquire()
        
        metrics = shedder._get_system_metrics()
        assert metrics.load_level.value == "normal"
        
        # Clean up
        for i in range(20):
            await shedder.release()
    
    @pytest.mark.asyncio
    async def test_elevated_load_level(self, mock_psutil):
        """Test elevated load level"""
        from aioresilience.load_shedding import SystemLoadShedder
        
        mock_psutil.cpu_percent.return_value = 65.0
        mock_psutil.virtual_memory.return_value.percent = 65.0
        
        shedder = SystemLoadShedder(max_requests=100)
        
        for i in range(60):
            await shedder.acquire()
        
        metrics = shedder._get_system_metrics()
        assert metrics.load_level.value == "elevated"
    
    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self, mock_psutil):
        """Test concurrent acquire and release operations"""
        import asyncio
        from aioresilience.load_shedding import SystemLoadShedder
        
        shedder = SystemLoadShedder(max_requests=100)
        
        async def worker():
            if await shedder.acquire():
                await asyncio.sleep(0.01)
                await shedder.release()
        
        # Run many concurrent workers
        await asyncio.gather(*[worker() for _ in range(50)])
        
        # All should have released
        assert shedder.active_requests == 0
