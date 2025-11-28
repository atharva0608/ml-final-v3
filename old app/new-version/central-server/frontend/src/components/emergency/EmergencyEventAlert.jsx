/**
 * Emergency Event Alert Component
 *
 * Displays critical alerts for AWS interruption notices:
 * - Rebalance recommendations (2-minute window)
 * - Termination notices (immediate)
 * Shows countdown timer and emergency replica status
 */
import React, { useState, useEffect } from 'react';
import { agentAPI } from '../../services/apiClient';

const EmergencyEventAlert = ({ agentId, agent, className = '' }) => {
    const [emergencyStatus, setEmergencyStatus] = useState(null);
    const [timeRemaining, setTimeRemaining] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!agentId) return;

        loadEmergencyStatus();
        // Refresh every 5 seconds during emergency
        const interval = setInterval(loadEmergencyStatus, 5000);
        return () => clearInterval(interval);
    }, [agentId]);

    useEffect(() => {
        if (!emergencyStatus || !emergencyStatus.notice_deadline) return;

        const updateTimer = () => {
            const deadline = new Date(emergencyStatus.notice_deadline);
            const now = new Date();
            const remaining = Math.max(0, Math.floor((deadline - now) / 1000));
            setTimeRemaining(remaining);

            if (remaining === 0) {
                loadEmergencyStatus(); // Refresh status when deadline reached
            }
        };

        updateTimer();
        const timer = setInterval(updateTimer, 1000);
        return () => clearInterval(timer);
    }, [emergencyStatus]);

    const loadEmergencyStatus = async () => {
        try {
            const response = await agentAPI.getEmergencyStatus(agentId);
            if (response.status === 'success') {
                setEmergencyStatus(response.data);
            }
        } catch (err) {
            console.error('Error loading emergency status:', err);
        } finally {
            setLoading(false);
        }
    };

    const formatCountdown = (seconds) => {
        if (seconds === null) return '--:--';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getSeverityConfig = (noticeStatus) => {
        switch (noticeStatus) {
            case 'rebalance':
                return {
                    color: 'yellow',
                    icon: '⚠️',
                    title: 'Rebalance Recommendation',
                    description: 'AWS recommends instance replacement. Emergency replica being prepared.',
                    bgColor: 'bg-yellow-50',
                    borderColor: 'border-yellow-400',
                    textColor: 'text-yellow-800'
                };
            case 'termination':
                return {
                    color: 'red',
                    icon: '🚨',
                    title: 'Termination Notice',
                    description: 'Instance will be terminated soon. Emergency failover in progress.',
                    bgColor: 'bg-red-50',
                    borderColor: 'border-red-500',
                    textColor: 'text-red-900'
                };
            default:
                return null;
        }
    };

    // Don't show if no emergency
    if (!emergencyStatus || emergencyStatus.notice_status === 'none') {
        return null;
    }

    const config = getSeverityConfig(emergencyStatus.notice_status);
    if (!config) return null;

    return (
        <div className={`${config.bgColor} border-l-4 ${config.borderColor} rounded-lg shadow-lg p-4 ${className}`}>
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center">
                    <span className="text-3xl mr-3">{config.icon}</span>
                    <div>
                        <h3 className={`text-lg font-bold ${config.textColor}`}>
                            {config.title}
                        </h3>
                        <p className="text-sm text-gray-700 mt-1">
                            {config.description}
                        </p>
                    </div>
                </div>

                {/* Countdown Timer */}
                {timeRemaining !== null && timeRemaining > 0 && (
                    <div className="text-right">
                        <div className="text-xs text-gray-600 uppercase tracking-wide">Time Remaining</div>
                        <div className={`text-3xl font-mono font-bold ${
                            timeRemaining < 60 ? 'text-red-600' : config.textColor
                        }`}>
                            {formatCountdown(timeRemaining)}
                        </div>
                    </div>
                )}
            </div>

            {/* Emergency Details */}
            <div className="grid grid-cols-2 gap-4 mt-4">
                {/* Notice Received */}
                <div className="bg-white bg-opacity-60 rounded p-3">
                    <div className="text-xs text-gray-600 font-medium mb-1">Notice Received</div>
                    <div className="text-sm font-semibold text-gray-900">
                        {new Date(emergencyStatus.notice_received_at).toLocaleTimeString()}
                    </div>
                </div>

                {/* Expected Deadline */}
                <div className="bg-white bg-opacity-60 rounded p-3">
                    <div className="text-xs text-gray-600 font-medium mb-1">Expected Deadline</div>
                    <div className="text-sm font-semibold text-gray-900">
                        {emergencyStatus.notice_deadline ?
                            new Date(emergencyStatus.notice_deadline).toLocaleTimeString() :
                            'Unknown'
                        }
                    </div>
                </div>
            </div>

            {/* Emergency Replica Status */}
            {emergencyStatus.emergency_replica && (
                <div className="mt-4 bg-white bg-opacity-60 rounded p-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-xs text-gray-600 font-medium mb-1">Emergency Replica</div>
                            <div className="text-sm font-semibold text-gray-900">
                                {emergencyStatus.emergency_replica.status.toUpperCase()}
                            </div>
                            {emergencyStatus.emergency_replica.pool_id && (
                                <div className="text-xs text-gray-600 mt-1">
                                    Pool: {emergencyStatus.emergency_replica.pool_id}
                                </div>
                            )}
                        </div>

                        {/* Status Indicator */}
                        <div>
                            {emergencyStatus.emergency_replica.status === 'ready' ? (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    ✓ Ready
                                </span>
                            ) : emergencyStatus.emergency_replica.status === 'launching' ? (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    🚀 Launching
                                </span>
                            ) : emergencyStatus.emergency_replica.status === 'syncing' ? (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                    ⚡ Syncing
                                </span>
                            ) : (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                    {emergencyStatus.emergency_replica.status}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Progress Bar for Syncing */}
                    {emergencyStatus.emergency_replica.status === 'syncing' &&
                     emergencyStatus.emergency_replica.sync_progress !== undefined && (
                        <div className="mt-3">
                            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                                <span>Sync Progress</span>
                                <span>{emergencyStatus.emergency_replica.sync_progress.toFixed(0)}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                                    style={{ width: `${emergencyStatus.emergency_replica.sync_progress}%` }}
                                ></div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Action Timeline */}
            {emergencyStatus.actions && emergencyStatus.actions.length > 0 && (
                <div className="mt-4">
                    <div className="text-xs text-gray-600 font-medium mb-2">Actions Taken</div>
                    <div className="space-y-2">
                        {emergencyStatus.actions.map((action, idx) => (
                            <div key={idx} className="flex items-start text-xs">
                                <span className="text-green-600 mr-2">✓</span>
                                <span className="text-gray-700">{action.description}</span>
                                <span className="text-gray-500 ml-auto">{action.time}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Critical Warning for Final Seconds */}
            {timeRemaining !== null && timeRemaining > 0 && timeRemaining < 30 && (
                <div className="mt-4 bg-red-100 border border-red-400 rounded p-3 animate-pulse">
                    <div className="text-sm font-bold text-red-900 flex items-center">
                        <span className="text-xl mr-2">⚠️</span>
                        CRITICAL: Less than 30 seconds remaining!
                    </div>
                </div>
            )}
        </div>
    );
};

export default EmergencyEventAlert;
