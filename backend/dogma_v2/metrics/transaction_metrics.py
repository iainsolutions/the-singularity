"""
Transaction performance metrics and monitoring system.

Provides:
- Transaction execution time tracking
- Memory usage monitoring
- Cache performance metrics
- Performance trend analysis
- Real-time performance dashboards
"""

import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics to collect"""

    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CACHE_HIT_RATE = "cache_hit_rate"
    TRANSACTION_COUNT = "transaction_count"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


@dataclass
class MetricDataPoint:
    """Individual metric data point"""

    timestamp: float
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class TransactionExecutionRecord:
    """Record of a transaction execution"""

    transaction_id: str
    transaction_name: str
    start_time: float
    end_time: float | None = None
    duration: float | None = None
    status: str = "started"
    memory_before: int | None = None
    memory_after: int | None = None
    memory_delta: int | None = None
    cache_hits: int = 0
    cache_misses: int = 0
    operations_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "completed", error_message: str | None = None):
        """Mark transaction as completed"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
        self.error_message = error_message

    def is_completed(self) -> bool:
        """Check if transaction is completed"""
        return self.end_time is not None


class MetricAggregator:
    """Aggregate metrics for analysis"""

    def __init__(self, window_size: int = 1000):
        """
        Initialize metric aggregator.

        Args:
            window_size: Size of sliding window for metrics
        """
        self.window_size = window_size
        self._data_points: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def add_data_point(
        self,
        metric_name: str,
        value: float,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ):
        """Add data point for metric"""
        data_point = MetricDataPoint(
            timestamp=time.time(), value=value, metadata=metadata or {}, tags=tags or {}
        )
        self._data_points[metric_name].append(data_point)

    def get_statistics(
        self, metric_name: str, time_window: float | None = None
    ) -> dict[str, float]:
        """
        Get statistics for metric.

        Args:
            metric_name: Name of metric
            time_window: Time window in seconds (None for all data)

        Returns:
            Dictionary with statistics
        """
        if metric_name not in self._data_points:
            return {}

        data_points = self._data_points[metric_name]

        # Filter by time window if specified
        if time_window:
            cutoff_time = time.time() - time_window
            data_points = [dp for dp in data_points if dp.timestamp >= cutoff_time]

        if not data_points:
            return {}

        values = [dp.value for dp in data_points]

        try:
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99),
            }
        except Exception as e:
            logger.error(f"Error calculating statistics for {metric_name}: {e}")
            return {"count": len(values), "error": str(e)}

    def _percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int((len(sorted_values) - 1) * percentile)
        return sorted_values[index]

    def get_all_metrics(self) -> list[str]:
        """Get list of all tracked metrics"""
        return list(self._data_points.keys())


class TransactionMetrics:
    """
    Transaction performance metrics tracker.

    Tracks execution times, memory usage, cache performance,
    and provides analytics and reporting.
    """

    def __init__(self, max_records: int = 10000, enable_real_time: bool = True):
        """
        Initialize transaction metrics.

        Args:
            max_records: Maximum number of execution records to keep
            enable_real_time: Enable real-time metric collection
        """
        self.max_records = max_records
        self.enable_real_time = enable_real_time

        # Execution records
        self._execution_records: deque = deque(maxlen=max_records)
        self._active_transactions: dict[str, TransactionExecutionRecord] = {}

        # Metric aggregators
        self._metric_aggregator = MetricAggregator()

        # Thread safety
        self._lock = threading.RLock()

        # Performance counters
        self._counters = defaultdict(int)

        logger.info("TransactionMetrics initialized")

    def start_transaction(
        self,
        transaction_id: str,
        transaction_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> TransactionExecutionRecord:
        """
        Start tracking transaction.

        Args:
            transaction_id: Unique transaction identifier
            transaction_name: Human-readable transaction name
            metadata: Additional metadata

        Returns:
            TransactionExecutionRecord for this transaction
        """
        with self._lock:
            # Get initial memory usage
            memory_before = self._get_memory_usage() if self.enable_real_time else None

            record = TransactionExecutionRecord(
                transaction_id=transaction_id,
                transaction_name=transaction_name,
                start_time=time.time(),
                memory_before=memory_before,
                metadata=metadata or {},
            )

            self._active_transactions[transaction_id] = record
            self._counters["transactions_started"] += 1

            logger.debug(
                f"Started tracking transaction: {transaction_name} ({transaction_id})"
            )
            return record

    def complete_transaction(
        self,
        transaction_id: str,
        status: str = "completed",
        error_message: str | None = None,
        cache_hits: int = 0,
        cache_misses: int = 0,
        operations_count: int = 0,
    ):
        """
        Complete transaction tracking.

        Args:
            transaction_id: Transaction identifier
            status: Final status ('completed', 'failed', 'rolled_back')
            error_message: Error message if failed
            cache_hits: Number of cache hits
            cache_misses: Number of cache misses
            operations_count: Number of operations performed
        """
        with self._lock:
            record = self._active_transactions.get(transaction_id)
            if not record:
                logger.warning(
                    f"Transaction {transaction_id} not found in active transactions"
                )
                return

            # Complete the record
            record.complete(status, error_message)

            # Update memory information
            if self.enable_real_time:
                record.memory_after = self._get_memory_usage()
                if record.memory_before and record.memory_after:
                    record.memory_delta = record.memory_after - record.memory_before

            # Update cache statistics
            record.cache_hits = cache_hits
            record.cache_misses = cache_misses
            record.operations_count = operations_count

            # Move to completed records
            del self._active_transactions[transaction_id]
            self._execution_records.append(record)

            # Update counters
            self._counters[f"transactions_{status}"] += 1

            # Add metrics to aggregator
            if record.duration:
                self._metric_aggregator.add_data_point(
                    MetricType.EXECUTION_TIME,
                    record.duration * 1000,  # Convert to milliseconds
                    metadata={"transaction_name": record.transaction_name},
                    tags={"status": status},
                )

            if record.memory_delta:
                self._metric_aggregator.add_data_point(
                    MetricType.MEMORY_USAGE,
                    record.memory_delta,
                    metadata={"transaction_name": record.transaction_name},
                )

            # Cache hit rate
            total_cache_requests = cache_hits + cache_misses
            if total_cache_requests > 0:
                hit_rate = cache_hits / total_cache_requests
                self._metric_aggregator.add_data_point(
                    MetricType.CACHE_HIT_RATE,
                    hit_rate,
                    metadata={"transaction_name": record.transaction_name},
                )

            logger.debug(
                f"Completed transaction: {record.transaction_name} "
                f"({transaction_id}) in {record.duration:.3f}s"
            )

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ):
        """
        Record custom metric.

        Args:
            metric_type: Type of metric
            value: Metric value
            metadata: Additional metadata
            tags: Metric tags
        """
        with self._lock:
            self._metric_aggregator.add_data_point(metric_type, value, metadata, tags)

    def get_transaction_statistics(
        self, time_window: float | None = None
    ) -> dict[str, Any]:
        """
        Get transaction execution statistics.

        Args:
            time_window: Time window in seconds (None for all data)

        Returns:
            Dictionary with comprehensive statistics
        """
        with self._lock:
            # Filter records by time window
            records = list(self._execution_records)
            if time_window:
                cutoff_time = time.time() - time_window
                records = [r for r in records if r.start_time >= cutoff_time]

            if not records:
                return {"total_transactions": 0}

            # Calculate statistics
            durations = [r.duration for r in records if r.duration]
            memory_deltas = [r.memory_delta for r in records if r.memory_delta]

            # Status distribution
            status_counts = defaultdict(int)
            transaction_name_counts = defaultdict(int)
            for record in records:
                status_counts[record.status] += 1
                transaction_name_counts[record.transaction_name] += 1

            # Cache statistics
            total_cache_hits = sum(r.cache_hits for r in records)
            total_cache_misses = sum(r.cache_misses for r in records)
            total_cache_requests = total_cache_hits + total_cache_misses

            return {
                "total_transactions": len(records),
                "status_distribution": dict(status_counts),
                "transaction_types": dict(transaction_name_counts),
                "execution_time": {
                    "count": len(durations),
                    "min_ms": min(durations) * 1000 if durations else 0,
                    "max_ms": max(durations) * 1000 if durations else 0,
                    "avg_ms": statistics.mean(durations) * 1000 if durations else 0,
                    "median_ms": statistics.median(durations) * 1000
                    if durations
                    else 0,
                    "p95_ms": self._percentile(durations, 0.95) * 1000
                    if durations
                    else 0,
                    "p99_ms": self._percentile(durations, 0.99) * 1000
                    if durations
                    else 0,
                },
                "memory_usage": {
                    "avg_delta_bytes": statistics.mean(memory_deltas)
                    if memory_deltas
                    else 0,
                    "max_delta_bytes": max(memory_deltas) if memory_deltas else 0,
                    "total_allocated_bytes": sum(d for d in memory_deltas if d > 0)
                    if memory_deltas
                    else 0,
                },
                "cache_performance": {
                    "hit_rate": total_cache_hits / total_cache_requests
                    if total_cache_requests > 0
                    else 0,
                    "total_hits": total_cache_hits,
                    "total_misses": total_cache_misses,
                    "total_requests": total_cache_requests,
                },
                "throughput": {
                    "transactions_per_second": len(records) / time_window
                    if time_window
                    else 0
                },
            }

    def _percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int((len(sorted_values) - 1) * percentile)
        return sorted_values[index]

    def get_performance_report(self, include_trends: bool = True) -> dict[str, Any]:
        """
        Get comprehensive performance report.

        Args:
            include_trends: Include trend analysis

        Returns:
            Detailed performance report
        """
        with self._lock:
            # Basic statistics
            stats_24h = self.get_transaction_statistics(
                time_window=24 * 3600
            )  # 24 hours
            stats_1h = self.get_transaction_statistics(time_window=3600)  # 1 hour
            stats_all = self.get_transaction_statistics()

            # Metric statistics
            metric_stats = {}
            for metric_name in self._metric_aggregator.get_all_metrics():
                metric_stats[metric_name] = self._metric_aggregator.get_statistics(
                    metric_name, time_window=3600
                )

            report = {
                "report_generated_at": time.time(),
                "statistics": {
                    "last_hour": stats_1h,
                    "last_24_hours": stats_24h,
                    "all_time": stats_all,
                },
                "metric_statistics": metric_stats,
                "active_transactions": len(self._active_transactions),
                "system_counters": dict(self._counters),
            }

            # Add trends if requested
            if include_trends:
                report["trends"] = self._calculate_trends()

            return report

    def _calculate_trends(self) -> dict[str, Any]:
        """Calculate performance trends"""
        try:
            # Get recent execution times for trend analysis
            recent_records = [
                r
                for r in self._execution_records
                if r.duration and r.start_time > time.time() - 3600  # Last hour
            ]

            if len(recent_records) < 10:
                return {"insufficient_data": True}

            # Split into two halves for trend comparison
            mid_point = len(recent_records) // 2
            first_half = recent_records[:mid_point]
            second_half = recent_records[mid_point:]

            first_half_avg = statistics.mean(r.duration for r in first_half) * 1000
            second_half_avg = statistics.mean(r.duration for r in second_half) * 1000

            performance_trend = (second_half_avg - first_half_avg) / first_half_avg

            return {
                "performance_trend_pct": performance_trend * 100,
                "trend_direction": "improving"
                if performance_trend < 0
                else "degrading",
                "first_half_avg_ms": first_half_avg,
                "second_half_avg_ms": second_half_avg,
                "sample_size": len(recent_records),
            }

        except Exception as e:
            logger.error(f"Error calculating trends: {e}")
            return {"error": str(e)}

    def _get_memory_usage(self) -> int:
        """Get current memory usage"""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            return 0

    def cleanup_old_records(self, max_age_hours: float = 24):
        """Remove old records to free memory"""
        cutoff_time = time.time() - (max_age_hours * 3600)

        with self._lock:
            # Filter out old records
            original_count = len(self._execution_records)
            filtered_records = deque(
                (r for r in self._execution_records if r.start_time >= cutoff_time),
                maxlen=self.max_records,
            )
            self._execution_records = filtered_records

            removed_count = original_count - len(self._execution_records)
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old transaction records")

    def get_active_transactions(self) -> list[dict[str, Any]]:
        """Get list of currently active transactions"""
        with self._lock:
            current_time = time.time()
            return [
                {
                    "transaction_id": record.transaction_id,
                    "transaction_name": record.transaction_name,
                    "duration_so_far": current_time - record.start_time,
                    "start_time": record.start_time,
                    "metadata": record.metadata,
                }
                for record in self._active_transactions.values()
            ]


class PerformanceMonitor:
    """Real-time performance monitoring with alerting"""

    def __init__(self, transaction_metrics: TransactionMetrics):
        """
        Initialize performance monitor.

        Args:
            transaction_metrics: TransactionMetrics instance to monitor
        """
        self.transaction_metrics = transaction_metrics
        self._alert_thresholds = {
            "avg_execution_time_ms": 1000,  # 1 second
            "memory_usage_mb": 500,  # 500 MB
            "error_rate_pct": 5,  # 5%
            "cache_hit_rate_min": 0.8,  # 80%
        }
        self._alert_callbacks: list[Callable] = []

    def add_alert_callback(self, callback: Callable[[str, dict[str, Any]], None]):
        """
        Add callback for performance alerts.

        Args:
            callback: Function called with (alert_type, alert_data)
        """
        self._alert_callbacks.append(callback)

    def check_performance_thresholds(self) -> list[dict[str, Any]]:
        """Check performance against thresholds and return alerts"""
        alerts = []
        stats = self.transaction_metrics.get_transaction_statistics(
            time_window=300
        )  # 5 minutes

        # Check execution time
        if (
            stats.get("execution_time", {}).get("avg_ms", 0)
            > self._alert_thresholds["avg_execution_time_ms"]
        ):
            alerts.append(
                {
                    "type": "high_execution_time",
                    "message": f"Average execution time exceeded {self._alert_thresholds['avg_execution_time_ms']}ms",
                    "current_value": stats["execution_time"]["avg_ms"],
                    "threshold": self._alert_thresholds["avg_execution_time_ms"],
                }
            )

        # Check error rate
        total_transactions = stats.get("total_transactions", 0)
        failed_transactions = stats.get("status_distribution", {}).get("failed", 0)
        if total_transactions > 0:
            error_rate = (failed_transactions / total_transactions) * 100
            if error_rate > self._alert_thresholds["error_rate_pct"]:
                alerts.append(
                    {
                        "type": "high_error_rate",
                        "message": f"Error rate exceeded {self._alert_thresholds['error_rate_pct']}%",
                        "current_value": error_rate,
                        "threshold": self._alert_thresholds["error_rate_pct"],
                    }
                )

        # Check cache hit rate
        cache_hit_rate = stats.get("cache_performance", {}).get("hit_rate", 1.0)
        if cache_hit_rate < self._alert_thresholds["cache_hit_rate_min"]:
            alerts.append(
                {
                    "type": "low_cache_hit_rate",
                    "message": f"Cache hit rate below {self._alert_thresholds['cache_hit_rate_min'] * 100}%",
                    "current_value": cache_hit_rate * 100,
                    "threshold": self._alert_thresholds["cache_hit_rate_min"] * 100,
                }
            )

        # Trigger callbacks
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert["type"], alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

        return alerts


# Global metrics instance
_transaction_metrics: TransactionMetrics | None = None
_performance_monitor: PerformanceMonitor | None = None


def get_transaction_metrics() -> TransactionMetrics:
    """Get global transaction metrics instance"""
    global _transaction_metrics
    if _transaction_metrics is None:
        _transaction_metrics = TransactionMetrics()
    return _transaction_metrics


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        metrics = get_transaction_metrics()
        _performance_monitor = PerformanceMonitor(metrics)
    return _performance_monitor
