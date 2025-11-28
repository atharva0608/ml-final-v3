/**
 * Downtime Analytics Card Component
 *
 * Displays switch downtime metrics and trends for a client.
 * Shows p95, avg, min, max downtime with 24-hour rolling window.
 */
import React, { useState, useEffect } from 'react';
import { clientAPI } from '../../services/apiClient';

const DowntimeCard = ({ clientId, className = '' }) => {
    const [downtimeData, setDowntimeData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [timeRange, setTimeRange] = useState(7); // days

    useEffect(() => {
        loadDowntimeData();
        // Refresh every minute
        const interval = setInterval(loadDowntimeData, 60000);
        return () => clearInterval(interval);
    }, [clientId, timeRange]);

    const loadDowntimeData = async () => {
        try {
            setLoading(true);
            setError(null);

            const data = await clientAPI.getDowntimeAnalytics(clientId, timeRange);

            if (data.status === 'success') {
                setDowntimeData(data.data);
            } else {
                throw new Error(data.error || 'Failed to load downtime data');
            }
        } catch (err) {
            console.error('Error loading downtime data:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (seconds) => {
        if (!seconds) return 'N/A';
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        return `${(seconds / 60).toFixed(1)}m`;
    };

    const getDowntimeStatus = (avgDowntime) => {
        if (avgDowntime < 10) return { color: 'green', label: 'Excellent' };
        if (avgDowntime < 30) return { color: 'blue', label: 'Good' };
        if (avgDowntime < 60) return { color: 'yellow', label: 'Fair' };
        return { color: 'red', label: 'Poor' };
    };

    if (loading) {
        return (
            <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
                <div className="animate-pulse">
                    <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
                    <div className="space-y-3">
                        <div className="h-16 bg-gray-200 rounded"></div>
                        <div className="h-16 bg-gray-200 rounded"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
                <div className="text-red-600">
                    <div className="font-semibold mb-2">⚠️ Error Loading Downtime Data</div>
                    <div className="text-sm">{error}</div>
                    <button
                        onClick={loadDowntimeData}
                        className="mt-3 text-sm text-blue-600 hover:text-blue-800"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    if (!downtimeData || downtimeData.total_switches === 0) {
        return (
            <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4 text-gray-800">⏱️ Switch Downtime</h3>
                <div className="text-center text-gray-500 py-8">
                    <div className="text-4xl mb-2">📊</div>
                    <div>No switch data available yet</div>
                    <div className="text-sm mt-1">Downtime metrics will appear after first switch</div>
                </div>
            </div>
        );
    }

    const status = getDowntimeStatus(downtimeData.avg_downtime_seconds);

    return (
        <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
            {/* Header with Time Range Selector */}
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800">⏱️ Switch Downtime</h3>
                <select
                    value={timeRange}
                    onChange={(e) => setTimeRange(Number(e.target.value))}
                    className="text-sm border border-gray-300 rounded px-2 py-1"
                >
                    <option value={1}>Last 24h</option>
                    <option value={7}>Last 7 days</option>
                    <option value={30}>Last 30 days</option>
                </select>
            </div>

            {/* Status Badge */}
            <div className="mb-4">
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium
                    ${status.color === 'green' ? 'bg-green-100 text-green-800' :
                      status.color === 'blue' ? 'bg-blue-100 text-blue-800' :
                      status.color === 'yellow' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'}`}
                >
                    {status.label}
                </span>
            </div>

            {/* Primary Metrics Grid */}
            <div className="grid grid-cols-2 gap-4 mb-4">
                {/* Average Downtime */}
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
                    <div className="text-sm text-blue-600 font-medium mb-1">Average</div>
                    <div className="text-2xl font-bold text-blue-900">
                        {formatDuration(downtimeData.avg_downtime_seconds)}
                    </div>
                </div>

                {/* P95 Downtime */}
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
                    <div className="text-sm text-purple-600 font-medium mb-1">P95</div>
                    <div className="text-2xl font-bold text-purple-900">
                        {formatDuration(downtimeData.p95_downtime_seconds)}
                    </div>
                </div>

                {/* Min Downtime */}
                <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
                    <div className="text-sm text-green-600 font-medium mb-1">Best</div>
                    <div className="text-xl font-bold text-green-900">
                        {formatDuration(downtimeData.min_downtime_seconds)}
                    </div>
                </div>

                {/* Max Downtime */}
                <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-lg p-4">
                    <div className="text-sm text-red-600 font-medium mb-1">Worst</div>
                    <div className="text-xl font-bold text-red-900">
                        {formatDuration(downtimeData.max_downtime_seconds)}
                    </div>
                </div>
            </div>

            {/* Additional Stats */}
            <div className="border-t border-gray-200 pt-4 mt-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                        <div className="text-2xl font-bold text-gray-900">{downtimeData.total_switches}</div>
                        <div className="text-xs text-gray-500 mt-1">Total Switches</div>
                    </div>
                    <div>
                        <div className="text-2xl font-bold text-green-600">
                            {downtimeData.successful_switches}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">Successful</div>
                    </div>
                    <div>
                        <div className="text-2xl font-bold text-red-600">
                            {downtimeData.failed_switches}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">Failed</div>
                    </div>
                </div>
            </div>

            {/* Success Rate */}
            {downtimeData.total_switches > 0 && (
                <div className="mt-4">
                    <div className="flex items-center justify-between text-sm mb-2">
                        <span className="text-gray-600">Success Rate</span>
                        <span className="font-semibold text-gray-900">
                            {((downtimeData.successful_switches / downtimeData.total_switches) * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                            className="bg-green-500 h-2 rounded-full transition-all duration-300"
                            style={{
                                width: `${(downtimeData.successful_switches / downtimeData.total_switches) * 100}%`
                            }}
                        ></div>
                    </div>
                </div>
            )}

            {/* Trend Indicator */}
            {downtimeData.trend && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">Trend (vs previous period)</span>
                        <span className={`font-semibold flex items-center ${
                            downtimeData.trend > 0 ? 'text-red-600' : 'text-green-600'
                        }`}>
                            {downtimeData.trend > 0 ? '↑' : '↓'}
                            {Math.abs(downtimeData.trend).toFixed(1)}%
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DowntimeCard;
