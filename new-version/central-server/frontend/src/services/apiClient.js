/**
 * API Client for AWS Spot Optimizer - Backend v6.0
 *
 * Complete API client with all endpoints aligned to operational runbook:
 * - Emergency flow endpoints (rebalance/termination notices)
 * - Operational metrics (downtime, emergency events, consolidation)
 * - ML model interface
 * - Idempotency support
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

/**
 * Base fetch wrapper with error handling and idempotency support
 */
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    // Add auth token if available
    const token = localStorage.getItem('adminToken');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Add idempotency key for POST/PUT/DELETE requests
    if (['POST', 'PUT', 'DELETE'].includes(options.method) && options.idempotencyKey) {
        headers['X-Request-ID'] = options.idempotencyKey;
    }

    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || errorData.message || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

/**
 * Generate UUID for idempotency keys
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// ============================================================================
// ADMIN OPERATIONS
// ============================================================================

export const adminAPI = {
    // Stats & Overview
    getStats: () => apiFetch('/api/admin/stats'),
    getSystemHealth: () => apiFetch('/api/admin/system-health'),
    getActivity: (limit = 50) => apiFetch(`/api/admin/activity?limit=${limit}`),
    search: (query) => apiFetch(`/api/admin/search?q=${encodeURIComponent(query)}`),

    // Clients
    getAllClients: () => apiFetch('/api/admin/clients'),
    getClientGrowth: () => apiFetch('/api/admin/clients/growth'),
    createClient: (data) => apiFetch('/api/admin/clients/create', {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
    deleteClient: (clientId) => apiFetch(`/api/admin/clients/${clientId}`, {
        method: 'DELETE',
        idempotencyKey: generateUUID()
    }),
    regenerateToken: (clientId) => apiFetch(`/api/admin/clients/${clientId}/regenerate-token`, {
        method: 'POST',
        idempotencyKey: generateUUID()
    }),
    getClientToken: (clientId) => apiFetch(`/api/admin/clients/${clientId}/token`),

    // Instances & Agents (Global)
    getAllInstances: () => apiFetch('/api/admin/instances'),
    getAllAgents: () => apiFetch('/api/admin/agents'),
    getAgentHealthSummary: () => apiFetch('/api/admin/agents/health-summary'),

    // Pool Statistics
    getPoolStatistics: () => apiFetch('/api/admin/pools/statistics'),

    // ML Models & Decision Engine
    uploadDecisionEngine: (file) => {
        const formData = new FormData();
        formData.append('engine', file);
        return apiFetch('/api/admin/decision-engine/upload', {
            method: 'POST',
            headers: {}, // Let browser set Content-Type for FormData
            body: formData,
            idempotencyKey: generateUUID()
        });
    },
    uploadMLModel: (file, modelName, modelVersion, modelType) => {
        const formData = new FormData();
        formData.append('model', file);
        formData.append('model_name', modelName);
        formData.append('model_version', modelVersion);
        formData.append('model_type', modelType);
        return apiFetch('/api/admin/ml-models/upload', {
            method: 'POST',
            headers: {},
            body: formData,
            idempotencyKey: generateUUID()
        });
    },
    activateMLModel: (modelId) => apiFetch('/api/admin/ml-models/activate', {
        method: 'POST',
        body: JSON.stringify({ model_id: modelId }),
        idempotencyKey: generateUUID()
    }),
    fallbackMLModel: () => apiFetch('/api/admin/ml-models/fallback', {
        method: 'POST',
        idempotencyKey: generateUUID()
    }),
    getMLModelSessions: () => apiFetch('/api/admin/ml-models/sessions'),

    // Operational Metrics (NEW)
    getOperationalMetrics: () => apiFetch('/api/admin/metrics/operational'),
    getConsolidationJobs: (days = 7) => apiFetch(`/api/admin/consolidation-jobs?days=${days}`),
    getEmergencyEventsSummary: (days = 30) => apiFetch(`/api/admin/emergency-events?days=${days}`),

    // Bulk Operations
    executeBulkOperation: (operation, params) => apiFetch('/api/admin/bulk/execute', {
        method: 'POST',
        body: JSON.stringify({ operation, ...params }),
        idempotencyKey: generateUUID()
    }),

    // Export
    exportGlobalStats: () => apiFetch('/api/admin/export/global-stats'),
};

// ============================================================================
// CLIENT OPERATIONS
// ============================================================================

export const clientAPI = {
    // Client Info
    validateToken: () => apiFetch('/api/client/validate'),
    getClientDetails: (clientId) => apiFetch(`/api/client/${clientId}`),
    getClientAgents: (clientId) => apiFetch(`/api/client/${clientId}/agents`),

    // Instances
    getInstances: (clientId) => apiFetch(`/api/client/${clientId}/instances`),
    getInstancePricing: (instanceId) => apiFetch(`/api/client/instances/${instanceId}/pricing`),
    getInstanceMetrics: (instanceId) => apiFetch(`/api/client/instances/${instanceId}/metrics`),
    getInstancePriceHistory: (instanceId, hours = 24) =>
        apiFetch(`/api/client/instances/${instanceId}/price-history?hours=${hours}`),
    getAvailableOptions: (instanceId) => apiFetch(`/api/client/instances/${instanceId}/available-options`),
    getInstanceLogs: (instanceId, limit = 100) =>
        apiFetch(`/api/client/instances/${instanceId}/logs?limit=${limit}`),
    getPoolVolatility: (instanceId) => apiFetch(`/api/client/instances/${instanceId}/pool-volatility`),

    // Instance Actions
    forceSwitch: (instanceId, targetPool, autoTerminate = true) => apiFetch(`/api/client/instances/${instanceId}/force-switch`, {
        method: 'POST',
        body: JSON.stringify({ target_pool: targetPool, auto_terminate: autoTerminate }),
        idempotencyKey: generateUUID()
    }),
    simulateSwitch: (instanceId, targetPool) => apiFetch(`/api/client/instances/${instanceId}/simulate-switch`, {
        method: 'POST',
        body: JSON.stringify({ target_pool: targetPool }),
        idempotencyKey: generateUUID()
    }),

    // Replicas
    getReplicas: (clientId) => apiFetch(`/api/client/${clientId}/replicas`),

    // Savings & Analytics
    getSavings: (clientId) => apiFetch(`/api/client/${clientId}/savings`),
    getSwitchHistory: (clientId, limit = 50) =>
        apiFetch(`/api/client/${clientId}/switch-history?limit=${limit}`),
    getChartData: (clientId) => apiFetch(`/api/client/${clientId}/stats/charts`),

    // Downtime Analytics (NEW)
    getDowntimeAnalytics: (clientId, days = 30) =>
        apiFetch(`/api/client/${clientId}/analytics/downtime?days=${days}`),

    // Pricing Alerts (NEW)
    createPricingAlert: (clientId, poolId, thresholdPrice) => apiFetch(`/api/client/${clientId}/pricing-alerts`, {
        method: 'POST',
        body: JSON.stringify({ pool_id: poolId, threshold_price: thresholdPrice }),
        idempotencyKey: generateUUID()
    }),

    // Export
    exportSavings: (clientId) => apiFetch(`/api/client/${clientId}/export/savings`),
    exportSwitchHistory: (clientId) => apiFetch(`/api/client/${clientId}/export/switch-history`),
};

// ============================================================================
// AGENT OPERATIONS
// ============================================================================

export const agentAPI = {
    // Agent Lifecycle
    register: (data) => apiFetch('/api/agents/register', {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
    heartbeat: (agentId, data) => apiFetch(`/api/agents/${agentId}/heartbeat`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),

    // Configuration
    getConfig: (agentId) => apiFetch(`/api/agents/${agentId}/config`),

    // Termination & Cleanup
    getInstancesToTerminate: (agentId) => apiFetch(`/api/agents/${agentId}/instances-to-terminate`),
    reportTermination: (agentId, data) => apiFetch(`/api/agents/${agentId}/termination-report`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),

    // Emergency Flows (NEW)
    reportRebalanceNotice: (agentId, noticeTime) => apiFetch(`/api/agents/${agentId}/rebalance-notice`, {
        method: 'POST',
        body: JSON.stringify({ notice_time: noticeTime }),
        idempotencyKey: generateUUID()
    }),
    reportTerminationNotice: (agentId, terminationTime) => apiFetch(`/api/agents/${agentId}/termination-notice`, {
        method: 'POST',
        body: JSON.stringify({ termination_time: terminationTime }),
        idempotencyKey: generateUUID()
    }),
    getEmergencyStatus: (agentId) => apiFetch(`/api/agents/${agentId}/emergency-status`),

    // Rebalance Recommendation
    handleRebalanceRecommendation: (agentId, data) => apiFetch(`/api/agents/${agentId}/rebalance-recommendation`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),

    // Replica
    getReplicaConfig: (agentId) => apiFetch(`/api/agents/${agentId}/replica-config`),

    // Decision Engine
    getDecision: (agentId, data) => apiFetch(`/api/agents/${agentId}/decide`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
    getSwitchRecommendation: (agentId) => apiFetch(`/api/agents/${agentId}/switch-recommendation`),
    issueSwitchCommand: (agentId, data) => apiFetch(`/api/agents/${agentId}/issue-switch-command`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),

    // Statistics
    getStatistics: (agentId) => apiFetch(`/api/agents/${agentId}/statistics`),

    // Commands
    getPendingCommands: (agentId) => apiFetch(`/api/agents/${agentId}/pending-commands`),
    markCommandExecuted: (agentId, commandId, result) => apiFetch(`/api/agents/${agentId}/commands/${commandId}/executed`, {
        method: 'POST',
        body: JSON.stringify(result),
        idempotencyKey: generateUUID()
    }),

    // Reporting
    sendPricingReport: (agentId, data) => apiFetch(`/api/agents/${agentId}/pricing-report`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
    sendSwitchReport: (agentId, data) => apiFetch(`/api/agents/${agentId}/switch-report`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
    sendCleanupReport: (agentId, data) => apiFetch(`/api/agents/${agentId}/cleanup-report`, {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: generateUUID()
    }),
};

// ============================================================================
// NOTIFICATIONS
// ============================================================================

export const notificationAPI = {
    getNotifications: () => apiFetch('/api/notifications'),
    markAsRead: (notificationId) => apiFetch(`/api/notifications/${notificationId}/mark-read`, {
        method: 'POST',
        idempotencyKey: generateUUID()
    }),
    markAllAsRead: () => apiFetch('/api/notifications/mark-all-read', {
        method: 'POST',
        idempotencyKey: generateUUID()
    }),
};

// ============================================================================
// REAL-TIME EVENTS (Server-Sent Events)
// ============================================================================

export const createEventSource = (clientId) => {
    const url = `${API_BASE_URL}/api/events/stream?client_id=${clientId}`;
    return new EventSource(url);
};

// ============================================================================
// HEALTH CHECK
// ============================================================================

export const healthAPI = {
    check: () => apiFetch('/health'),
    root: () => apiFetch('/'),
};

// ============================================================================
// EXPORT ALL
// ============================================================================

export default {
    admin: adminAPI,
    client: clientAPI,
    agent: agentAPI,
    notifications: notificationAPI,
    health: healthAPI,
    createEventSource,
};
