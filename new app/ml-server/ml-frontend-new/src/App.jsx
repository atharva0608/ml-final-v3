import React, { useState, useEffect, useRef } from 'react';
import {
    Activity, Server, Brain, DollarSign, Database, LayoutDashboard, Settings,
    Play, Pause, RefreshCw, AlertTriangle, CheckCircle, Search, Zap, TrendingUp,
    Box, Cpu, HardDrive, ChevronLeft, Terminal, BarChart2, Clock, Download,
    Layers, GitBranch, Filter
} from 'lucide-react';

/**
 * FAKE API SERVICE
 */
const FakeApi = {
    delay: (ms) => new Promise(resolve => setTimeout(resolve, ms)),

    async getOverviewStats() {
        await this.delay(600);
        const response = await fetch('/api/v1/ml/dashboard/stats');
        const data = await response.json();
        return data.stats;
    },

    async getDecisionEngines() {
        await this.delay(800);
        const response = await fetch('/api/v1/decision-engines');
        const data = await response.json();
        return data.engines;
    },

    async getModels() {
        await this.delay(500);
        const response = await fetch('/api/v1/models');
        const data = await response.json();
        return data.models;
    },

    async getLivePredictions() {
        await this.delay(1000);
        const response = await fetch('/api/v1/predictions/live');
        const data = await response.json();
        return data.predictions;
    },

    async getSpotPrices() {
        await this.delay(700);
        const response = await fetch('/api/v1/pricing/current');
        const data = await response.json();
        return data.prices;
    },

    async getGapFillJobs() {
        await this.delay(600);
        const response = await fetch('/api/v1/data-gaps/history');
        const data = await response.json();
        return data.jobs || [];
    },

    async toggleEngine(id) {
        await this.delay(800);
        return true;
    },

    async triggerModelRefresh(modelId) {
        await this.delay(1500);
        return { success: true };
    }
};

/**
 * CUSTOM CHARTING
 */
const LineChart = ({ data, height = 300, colorActual = "#6366f1", colorPredicted = "#10b981" }) => {
    const containerRef = useRef(null);
    const [width, setWidth] = useState(600);
    const [hoverIndex, setHoverIndex] = useState(null);

    useEffect(() => {
        if (containerRef.current) {
            setWidth(containerRef.current.offsetWidth);
        }
        const handleResize = () => {
            if (containerRef.current) setWidth(containerRef.current.offsetWidth);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const padding = { top: 20, right: 20, bottom: 40, left: 50 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;

    const maxVal = Math.max(...data.map(d => Math.max(d.actual || 0, d.predicted || 0))) * 1.1;
    const minVal = Math.min(...data.map(d => Math.min(d.actual || 0, d.predicted || 0))) * 0.9;

    const getX = (index) => padding.left + (index / (data.length - 1)) * graphWidth;
    const getY = (val) => padding.top + graphHeight - ((val - minVal) / (maxVal - minVal)) * graphHeight;

    const createPath = (key) => {
        return data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(d[key] || 0)}`).join(' ');
    };

    return (
        <div ref={containerRef} style={{ position: 'relative', width: '100%', userSelect: 'none' }}>
            <svg width={width} height={height} style={{ overflow: 'visible' }}>
                {/* Grid & Axis */}
                {[0, 0.5, 1].map((tick) => {
                    const y = padding.top + graphHeight - (tick * graphHeight);
                    const val = minVal + tick * (maxVal - minVal);
                    return (
                        <g key={tick}>
                            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e2e8f0" strokeDasharray="4 4" />
                            <text x={padding.left - 10} y={y + 4} textAnchor="end" fontSize="10" fill="#64748b">${val.toFixed(3)}</text>
                        </g>
                    );
                })}
                {/* Lines */}
                <path d={createPath('actual')} fill="none" stroke={colorActual} strokeWidth="2" />
                <path d={createPath('predicted')} fill="none" stroke={colorPredicted} strokeWidth="2" strokeDasharray="5 5" />

                {/* Hover Interaction */}
                {data.map((d, i) => (
                    <rect key={i} x={getX(i) - 5} y={padding.top} width={10} height={graphHeight} fill="transparent"
                        onMouseEnter={() => setHoverIndex(i)} onMouseLeave={() => setHoverIndex(null)}
                    />
                ))}
                {hoverIndex !== null && (
                    <g>
                        <line x1={getX(hoverIndex)} y1={padding.top} x2={getX(hoverIndex)} y2={height - padding.bottom} stroke="#94a3b8" />
                        <circle cx={getX(hoverIndex)} cy={getY(data[hoverIndex].actual || 0)} r="4" fill={colorActual} stroke="white" strokeWidth="2" />
                        <circle cx={getX(hoverIndex)} cy={getY(data[hoverIndex].predicted || 0)} r="4" fill={colorPredicted} stroke="white" strokeWidth="2" />
                    </g>
                )}
            </svg>
            {/* Tooltip */}
            {hoverIndex !== null && (
                <div style={{
                    position: 'absolute',
                    background: 'white',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                    border: '1px solid #e2e8f0',
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    zIndex: 10,
                    pointerEvents: 'none',
                    left: Math.min(getX(hoverIndex) + 10, width - 120) + 'px',
                    top: padding.top + 'px'
                }}>
                    <p style={{ fontWeight: 'bold', marginBottom: '4px' }}>{data[hoverIndex].timestamp}</p>
                    <div style={{ color: '#4f46e5' }}>Act: ${(data[hoverIndex].actual || 0).toFixed(4)}</div>
                    <div style={{ color: '#10b981' }}>Pre: ${(data[hoverIndex].predicted || 0).toFixed(4)}</div>
                </div>
            )}
        </div>
    );
};

// Helper Components
const Card = ({ children, className = "", style = {} }) => (
    <div style={{
        background: 'white',
        borderRadius: '12px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        border: '1px solid #e2e8f0',
        ...style
    }} className={className}>{children}</div>
);

const Badge = ({ status }) => {
    const styles = {
        active: { background: '#d1fae5', color: '#047857' },
        deployed: { background: '#d1fae5', color: '#047857' },
        completed: { background: '#dbeafe', color: '#1e40af' },
        paused: { background: '#fef3c7', color: '#b45309' },
        training: { background: '#e9d5ff', color: '#7c3aed' },
        degraded: { background: '#ffe4e6', color: '#be123c' },
        failed: { background: '#ffe4e6', color: '#be123c' },
        processing: { background: '#e0e7ff', color: '#4338ca' },
    };
    const badgeStyle = styles[status] || { background: '#f1f5f9', color: '#475569' };
    return (
        <span style={{
            ...badgeStyle,
            padding: '2px 10px',
            borderRadius: '9999px',
            fontSize: '11px',
            fontWeight: 500,
            textTransform: 'uppercase',
            display: 'inline-block'
        }}>
            {status}
        </span>
    );
};

// SUB-PAGES

// 1. Dashboard / Overview
const Overview = () => {
    const [stats, setStats] = useState(null);
    useEffect(() => {
        FakeApi.getOverviewStats().then(setStats).catch(err => {
            console.error('Failed to fetch stats:', err);
            setStats({
                totalSavings: 4520.50,
                predictionsToday: 17892,
                activeEngines: 5,
                clusterHealth: 98,
                costTrend: [4200, 4350, 4100, 4400, 4520.50],
                alerts: []
            });
        });
    }, []);

    if (!stats) return <div style={{ padding: '32px', textAlign: 'center' }}><RefreshCw className="animate-spin" style={{ display: 'inline', color: '#4f46e5' }} /></div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div><p style={{ color: '#64748b', fontSize: '14px' }}>Monthly Savings</p><h3 style={{ fontSize: '24px', fontWeight: 'bold' }}>${stats.totalSavings}</h3></div>
                        <DollarSign style={{ color: '#10b981', width: '32px', height: '32px', background: '#ecfdf5', padding: '6px', borderRadius: '8px' }} />
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div><p style={{ color: '#64748b', fontSize: '14px' }}>Predictions (24h)</p><h3 style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.predictionsToday}</h3></div>
                        <Brain style={{ color: '#6366f1', width: '32px', height: '32px', background: '#eef2ff', padding: '6px', borderRadius: '8px' }} />
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div><p style={{ color: '#64748b', fontSize: '14px' }}>Active Engines</p><h3 style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.activeEngines}/7</h3></div>
                        <Cpu style={{ color: '#d97706', width: '32px', height: '32px', background: '#fffbeb', padding: '6px', borderRadius: '8px' }} />
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div><p style={{ color: '#64748b', fontSize: '14px' }}>Cluster Health</p><h3 style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.clusterHealth}%</h3></div>
                        <Activity style={{ color: '#e11d48', width: '32px', height: '32px', background: '#fff1f2', padding: '6px', borderRadius: '8px' }} />
                    </div>
                </Card>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                <Card style={{ padding: '24px' }}>
                    <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px' }}>Cost Trend</h3>
                    <div style={{ height: '192px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '8px' }}>
                        {stats.costTrend.map((v, i) => (
                            <div key={i} style={{
                                background: '#e0e7ff',
                                width: '100%',
                                borderTopLeftRadius: '4px',
                                borderTopRightRadius: '4px',
                                position: 'relative',
                                height: `${(v / 5000) * 100}%`,
                                cursor: 'pointer'
                            }} onMouseEnter={(e) => e.currentTarget.style.background = '#c7d2fe'} onMouseLeave={(e) => e.currentTarget.style.background = '#e0e7ff'}>
                            </div>
                        ))}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '12px', color: '#94a3b8' }}>
                        <span>5 days ago</span>
                        <span>Today</span>
                    </div>
                </Card>

                <Card style={{ padding: '24px' }}>
                    <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px' }}>System Alerts</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', padding: '12px', background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: '8px' }}>
                            <AlertTriangle style={{ color: '#d97706', width: '20px', height: '20px', marginRight: '12px' }} />
                            <div>
                                <p style={{ fontSize: '14px', fontWeight: 600, color: '#78350f' }}>Noisy Neighbor Detected</p>
                                <p style={{ fontSize: '12px', color: '#b45309' }}>Pod 'data-proc-7x' is consuming excessive CPU.</p>
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', padding: '12px', background: '#f8fafc', border: '1px solid #f1f5f9', borderRadius: '8px' }}>
                            <RefreshCw style={{ color: '#475569', width: '20px', height: '20px', marginRight: '12px' }} />
                            <div>
                                <p style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>Model Retraining</p>
                                <p style={{ fontSize: '12px', color: '#64748b' }}>SpotPredictor v1.0.5 is currently training.</p>
                            </div>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
};

// 2. Live Predictions
const LivePredictions = () => {
    const [predictions, setPredictions] = useState([]);
    useEffect(() => {
        FakeApi.getLivePredictions().then(setPredictions).catch(err => {
            console.error('Failed to fetch predictions:', err);
            setPredictions([]);
        });
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#0f172a' }}>Live Predictions</h2>
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Real-time inference stream from PricePrediction model</p>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Badge status="active" />
                    <span style={{ fontSize: '14px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Activity style={{ width: '16px', height: '16px' }} /> 45ms latency
                    </span>
                </div>
            </div>

            <Card style={{ padding: '24px' }}>
                <h3 style={{ fontWeight: 600, color: '#334155', marginBottom: '24px' }}>Predicted vs Actual Spot Price (Last 24h)</h3>
                <LineChart data={predictions} height={350} />
            </Card>

            <Card>
                <div style={{ padding: '16px 24px', borderBottom: '1px solid #f1f5f9', background: '#f8fafc' }}>
                    <h3 style={{ fontWeight: 600, color: '#334155' }}>Recent Inference Logs</h3>
                </div>
                <table style={{ width: '100%', fontSize: '14px', textAlign: 'left' }}>
                    <thead style={{ background: '#f8fafc', color: '#64748b' }}>
                        <tr>
                            <th style={{ padding: '12px 24px' }}>Timestamp</th>
                            <th style={{ padding: '12px 24px' }}>Feature Hash</th>
                            <th style={{ padding: '12px 24px' }}>Predicted</th>
                            <th style={{ padding: '12px 24px' }}>Confidence</th>
                        </tr>
                    </thead>
                    <tbody style={{ borderTop: '1px solid #f1f5f9' }}>
                        {predictions.slice(0, 5).map((p, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }} onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'} onMouseLeave={(e) => e.currentTarget.style.background = 'white'}>
                                <td style={{ padding: '12px 24px', fontFamily: 'monospace', color: '#475569' }}>{p.timestamp}</td>
                                <td style={{ padding: '12px 24px', fontFamily: 'monospace', fontSize: '12px', color: '#94a3b8' }}>{p.feature_hash}</td>
                                <td style={{ padding: '12px 24px', fontWeight: 500, color: '#059669' }}>${(p.predicted || 0).toFixed(4)}</td>
                                <td style={{ padding: '12px 24px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <div style={{ width: '64px', height: '6px', background: '#e2e8f0', borderRadius: '9999px', overflow: 'hidden' }}>
                                            <div style={{ height: '100%', background: '#6366f1', width: `${(p.confidence || 0) * 100}%` }} />
                                        </div>
                                        <span style={{ fontSize: '12px', color: '#64748b' }}>{((p.confidence || 0) * 100).toFixed(0)}%</span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>
        </div>
    );
};

// 3. Decision Engines
const DecisionEngines = () => {
    const [engines, setEngines] = useState([]);
    useEffect(() => {
        FakeApi.getDecisionEngines().then(setEngines).catch(err => {
            console.error('Failed to fetch decision engines:', err);
            setEngines([]);
        });
    }, []);

    const toggle = (id) => {
        setEngines(prev => prev.map(e => e.id === id ? { ...e, status: e.status === 'active' ? 'paused' : 'active' } : e));
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#0f172a' }}>Decision Engines</h2>
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Control autonomous optimization agents</p>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {engines.map(engine => (
                    <Card key={engine.id} style={{ padding: '24px', display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: '16px', transition: 'box-shadow 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)'} onMouseLeave={(e) => e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)'}>
                        <div style={{ display: 'flex', gap: '16px' }}>
                            <div style={{
                                padding: '12px',
                                borderRadius: '8px',
                                height: 'fit-content',
                                background: engine.type === 'optimization' ? '#ecfdf5' : engine.type === 'remediation' ? '#fff1f2' : '#dbeafe',
                                color: engine.type === 'optimization' ? '#047857' : engine.type === 'remediation' ? '#be123c' : '#1e40af'
                            }}>
                                {engine.type === 'optimization' ? <DollarSign style={{ width: '24px', height: '24px' }} /> :
                                    engine.type === 'remediation' ? <AlertTriangle style={{ width: '24px', height: '24px' }} /> :
                                        <Search style={{ width: '24px', height: '24px' }} />}
                            </div>
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <h3 style={{ fontWeight: 'bold', fontSize: '18px', color: '#1e293b' }}>{engine.name}</h3>
                                    <Badge status={engine.status} />
                                </div>
                                <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>{engine.description}</p>
                                <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '12px', color: '#94a3b8', fontWeight: 500 }}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Clock style={{ width: '12px', height: '12px' }} /> Last Run: {engine.lastRun}</span>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#475569', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>Impact: {engine.impact}</span>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={() => toggle(engine.id)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '8px 16px',
                                borderRadius: '8px',
                                fontWeight: 500,
                                border: 'none',
                                cursor: 'pointer',
                                transition: 'background 0.2s',
                                background: engine.status === 'active' ? '#f1f5f9' : '#4f46e5',
                                color: engine.status === 'active' ? '#475569' : 'white'
                            }}
                        >
                            {engine.status === 'active' ? <Pause style={{ width: '16px', height: '16px' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
                            {engine.status === 'active' ? 'Pause Agent' : 'Resume Agent'}
                        </button>
                    </Card>
                ))}
            </div>
        </div>
    );
};

// 4. Model Management
const ModelManagement = () => {
    const [models, setModels] = useState([]);
    useEffect(() => {
        FakeApi.getModels().then(setModels).catch(err => {
            console.error('Failed to fetch models:', err);
            setModels([]);
        });
    }, []);

    const handleRefresh = async (id) => {
        alert(`Triggered retraining pipeline for ${id}`);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#0f172a' }}>Model Registry</h2>
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Manage lifecycles and retraining pipelines</p>
                </div>
                <button style={{ background: '#4f46e5', color: 'white', padding: '8px 16px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Download style={{ width: '16px', height: '16px' }} /> Import Model
                </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                {models.map(model => (
                    <Card key={model.id} style={{ padding: '24px', position: 'relative' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                            <div style={{ padding: '8px', background: '#eef2ff', borderRadius: '8px', color: '#6366f1' }}>
                                <Layers style={{ width: '24px', height: '24px' }} />
                            </div>
                            <Badge status={model.status} />
                        </div>

                        <h3 style={{ fontWeight: 'bold', fontSize: '18px', color: '#0f172a' }}>{model.name}</h3>
                        <p style={{ fontSize: '12px', color: '#64748b', fontFamily: 'monospace', marginBottom: '16px' }}>{model.version}</p>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '14px', marginBottom: '24px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: '#64748b' }}>Framework</span>
                                <span style={{ fontWeight: 500, color: '#334155', textTransform: 'capitalize' }}>{model.framework}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: '#64748b' }}>Accuracy</span>
                                <span style={{ fontWeight: 500, color: '#059669' }}>{(model.accuracy * 100).toFixed(1)}%</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: '#64748b' }}>Last Trained</span>
                                <span style={{ fontWeight: 500, color: '#334155' }}>{model.lastTrained}</span>
                            </div>
                        </div>

                        <button
                            onClick={() => handleRefresh(model.id)}
                            style={{ width: '100%', padding: '8px', border: '1px solid #c7d2fe', color: '#6366f1', borderRadius: '8px', fontSize: '14px', fontWeight: 500, background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                        >
                            <RefreshCw style={{ width: '16px', height: '16px' }} /> Trigger Retrain
                        </button>
                    </Card>
                ))}
            </div>
        </div>
    );
};

// 5. Data Gap Filler
const DataOps = () => {
    const [jobs, setJobs] = useState([]);
    useEffect(() => {
        FakeApi.getGapFillJobs().then(setJobs).catch(err => {
            console.error('Failed to fetch data gaps:', err);
            setJobs([]);
        });
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#0f172a' }}>Data Ops: Gap Filler</h2>
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Manage missing data interpolation jobs</p>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                <Card style={{ padding: '24px' }}>
                    <h3 style={{ fontWeight: 'bold', color: '#0f172a', marginBottom: '16px' }}>Start New Gap Analysis</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#64748b', marginBottom: '4px' }}>Target Dataset</label>
                            <select style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px', fontSize: '14px', background: 'white' }}>
                                <option>spot_market_prices</option>
                                <option>node_metrics</option>
                                <option>application_latency</option>
                            </select>
                        </div>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#64748b', marginBottom: '4px' }}>Fill Strategy</label>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button style={{ flex: 1, padding: '8px', background: '#eef2ff', border: '1px solid #c7d2fe', color: '#4338ca', borderRadius: '8px', fontSize: '12px', fontWeight: 500, cursor: 'pointer' }}>Interpolation</button>
                                <button style={{ flex: 1, padding: '8px', background: 'white', border: '1px solid #e2e8f0', color: '#475569', borderRadius: '8px', fontSize: '12px', fontWeight: 500, cursor: 'pointer' }}>Proxy Fetch</button>
                            </div>
                        </div>
                        <button style={{ width: '100%', background: '#4f46e5', color: 'white', padding: '10px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, border: 'none', cursor: 'pointer', marginTop: '8px' }}>
                            Run Analysis
                        </button>
                    </div>
                </Card>

                <Card>
                    <div style={{ padding: '16px 24px', borderBottom: '1px solid #f1f5f9', background: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontWeight: 600, color: '#334155' }}>Recent Jobs</h3>
                        <button style={{ fontSize: '12px', color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>View All</button>
                    </div>
                    <div>
                        {jobs.map(job => (
                            <div key={job.id} style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9' }} onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'} onMouseLeave={(e) => e.currentTarget.style.background = 'white'}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                    <div style={{ padding: '8px', borderRadius: '9999px', background: job.status === 'processing' ? '#fef3c7' : '#d1fae5', color: job.status === 'processing' ? '#d97706' : '#059669' }}>
                                        <RefreshCw className={job.status === 'processing' ? 'animate-spin' : ''} style={{ width: '16px', height: '16px' }} />
                                    </div>
                                    <div>
                                        <p style={{ fontWeight: 500, color: '#0f172a', fontSize: '14px' }}>{job.dataset}</p>
                                        <p style={{ fontSize: '12px', color: '#64748b' }}>Strategy: {job.strategy} • {job.created_at}</p>
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ display: 'block', fontWeight: 'bold', color: '#334155' }}>{job.filled_count} pts</span>
                                    <Badge status={job.status} />
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
        </div>
    );
};

// 6. Pricing Data
const PricingData = () => {
    const [prices, setPrices] = useState([]);
    useEffect(() => {
        FakeApi.getSpotPrices().then(setPrices).catch(err => {
            console.error('Failed to fetch pricing:', err);
            setPrices([]);
        });
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#0f172a' }}>Spot Pricing</h2>
                    <p style={{ color: '#64748b', fontSize: '14px' }}>Real-time market data across regions</p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input type="text" placeholder="Filter by instance type..." style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 12px', fontSize: '14px' }} />
                    <button style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '8px', background: 'white', cursor: 'pointer' }}><Filter style={{ width: '16px', height: '16px', color: '#64748b' }} /></button>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                {prices.map((p, i) => (
                    <Card key={i} style={{ padding: '16px', transition: 'border-color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.borderColor = '#c7d2fe'} onMouseLeave={(e) => e.currentTarget.style.borderColor = '#e2e8f0'}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                            <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#64748b', textTransform: 'uppercase' }}>{p.region}</span>
                            <span style={{ fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', color: p.trend === 'down' ? '#059669' : p.trend === 'up' ? '#e11d48' : '#64748b' }}>
                                {p.trend === 'down' ? <TrendingUp style={{ width: '12px', height: '12px', marginRight: '4px', transform: 'rotate(180deg)' }} /> :
                                    p.trend === 'up' ? <TrendingUp style={{ width: '12px', height: '12px', marginRight: '4px' }} /> : null}
                                {p.trend}
                            </span>
                        </div>
                        <h3 style={{ fontWeight: 'bold', fontSize: '18px', color: '#0f172a' }}>{p.instanceType}</h3>
                        <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '12px' }}>{p.az}</p>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                            <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#0f172a' }}>${p.price}</span>
                            <span style={{ fontSize: '12px', color: '#64748b' }}>/hr</span>
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    );
};

// APP SHELL
const SidebarLink = ({ icon: Icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '10px 12px',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            cursor: 'pointer',
            background: active ? '#eef2ff' : 'transparent',
            color: active ? '#4338ca' : '#475569',
            transition: 'all 0.2s'
        }}
        onMouseEnter={(e) => !active && (e.currentTarget.style.background = '#f8fafc')}
        onMouseLeave={(e) => !active && (e.currentTarget.style.background = 'transparent')}
    >
        <Icon style={{ width: '20px', height: '20px', color: active ? '#6366f1' : '#94a3b8' }} />
        {label}
    </button>
);

const App = () => {
    const [view, setView] = useState('overview');

    return (
        <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', fontFamily: 'system-ui, -apple-system, sans-serif', color: '#0f172a' }}>
            {/* Sidebar */}
            <aside style={{ width: '256px', background: 'white', borderRight: '1px solid #e2e8f0', position: 'fixed', height: '100%', zIndex: 10, display: 'flex', flexDirection: 'column' }}>
                <div style={{ height: '64px', display: 'flex', alignItems: 'center', padding: '0 24px', borderBottom: '1px solid #e2e8f0' }}>
                    <div style={{ width: '32px', height: '32px', background: '#4f46e5', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                        <Server style={{ width: '20px', height: '20px', color: 'white' }} />
                    </div>
                    <span style={{ fontWeight: 'bold', fontSize: '18px', letterSpacing: '-0.02em' }}>ML Server</span>
                </div>

                <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, overflowY: 'auto' }}>
                    <p style={{ padding: '0 12px', fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', marginTop: '8px' }}>Core</p>
                    <SidebarLink icon={LayoutDashboard} label="Overview" active={view === 'overview'} onClick={() => setView('overview')} />
                    <SidebarLink icon={Zap} label="Live Predictions" active={view === 'predictions'} onClick={() => setView('predictions')} />
                    <SidebarLink icon={Cpu} label="Decision Engines" active={view === 'engines'} onClick={() => setView('engines')} />

                    <p style={{ padding: '0 12px', fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', marginTop: '24px' }}>ML Ops</p>
                    <SidebarLink icon={Layers} label="Model Registry" active={view === 'models'} onClick={() => setView('models')} />
                    <SidebarLink icon={Database} label="Data Gap Filler" active={view === 'data'} onClick={() => setView('data')} />
                    <SidebarLink icon={DollarSign} label="Pricing Data" active={view === 'pricing'} onClick={() => setView('pricing')} />
                </div>

                <div style={{ padding: '16px', borderTop: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px', borderRadius: '8px', cursor: 'pointer' }} onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                        <div style={{ width: '32px', height: '32px', background: '#e9d5ff', color: '#7c3aed', borderRadius: '9999px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '12px' }}>A</div>
                        <div>
                            <p style={{ fontSize: '14px', fontWeight: 500 }}>Admin</p>
                            <p style={{ fontSize: '12px', color: '#64748b' }}>admin@mlserver.io</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, marginLeft: '256px', display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
                <header style={{ height: '64px', background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(10px)', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 10, padding: '0 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#64748b', background: '#f1f5f9', padding: '4px 12px', borderRadius: '9999px' }}>
                        <GitBranch style={{ width: '16px', height: '16px' }} />
                        Branch: <span style={{ fontFamily: 'monospace', fontWeight: 500, color: '#334155' }}>main</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 500, color: '#059669', background: '#ecfdf5', padding: '4px 8px', borderRadius: '9999px', border: '1px solid #d1fae5' }}>
                            <div className="animate-pulse" style={{ width: '6px', height: '6px', borderRadius: '9999px', background: '#10b981' }} />
                            Connected
                        </div>
                        <button style={{ padding: '8px', borderRadius: '9999px', border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8' }} onMouseEnter={(e) => e.currentTarget.style.background = '#f1f5f9'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                            <Settings style={{ width: '20px', height: '20px' }} />
                        </button>
                    </div>
                </header>

                <div style={{ padding: '32px', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
                    {view === 'overview' && <Overview />}
                    {view === 'predictions' && <LivePredictions />}
                    {view === 'engines' && <DecisionEngines />}
                    {view === 'models' && <ModelManagement />}
                    {view === 'data' && <DataOps />}
                    {view === 'pricing' && <PricingData />}
                </div>
            </main>
        </div>
    );
};

export default App;
