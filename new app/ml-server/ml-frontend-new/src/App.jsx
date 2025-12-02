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

    const createAreaPath = (key) => {
        const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(d[key] || 0)}`).join(' ');
        return `${linePath} L ${getX(data.length - 1)} ${height - padding.bottom} L ${padding.left} ${height - padding.bottom} Z`;
    };

    return (
        <div ref={containerRef} style={{ position: 'relative', width: '100%', userSelect: 'none' }}>
            <svg width={width} height={height} style={{ overflow: 'visible' }}>
                <defs>
                    <linearGradient id="gradientActual" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--primary-500)" stopOpacity="0.2" />
                        <stop offset="100%" stopColor="var(--primary-500)" stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* Grid & Axis */}
                {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
                    const y = padding.top + graphHeight - (tick * graphHeight);
                    const val = minVal + tick * (maxVal - minVal);
                    return (
                        <g key={tick}>
                            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="var(--slate-200)" strokeDasharray="4 4" />
                            <text x={padding.left - 12} y={y + 4} textAnchor="end" fontSize="11" fill="var(--slate-400)" fontWeight="500">${val.toFixed(3)}</text>
                        </g>
                    );
                })}

                {/* Areas */}
                <path d={createAreaPath('actual')} fill="url(#gradientActual)" />

                {/* Lines */}
                <path d={createPath('actual')} fill="none" stroke="var(--primary-500)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <path d={createPath('predicted')} fill="none" stroke="var(--success-500)" strokeWidth="2" strokeDasharray="6 6" strokeLinecap="round" />

                {/* Hover Interaction */}
                {data.map((d, i) => (
                    <rect key={i} x={getX(i) - 10} y={padding.top} width={20} height={graphHeight} fill="transparent"
                        onMouseEnter={() => setHoverIndex(i)} onMouseLeave={() => setHoverIndex(null)}
                        style={{ cursor: 'crosshair' }}
                    />
                ))}

                {hoverIndex !== null && (
                    <g>
                        <line x1={getX(hoverIndex)} y1={padding.top} x2={getX(hoverIndex)} y2={height - padding.bottom} stroke="var(--slate-300)" strokeWidth="1" />
                        <circle cx={getX(hoverIndex)} cy={getY(data[hoverIndex].actual || 0)} r="6" fill="var(--primary-500)" stroke="white" strokeWidth="3" />
                        <circle cx={getX(hoverIndex)} cy={getY(data[hoverIndex].predicted || 0)} r="6" fill="var(--success-500)" stroke="white" strokeWidth="3" />
                    </g>
                )}
            </svg>

            {/* Tooltip */}
            {hoverIndex !== null && (
                <div style={{
                    position: 'absolute',
                    background: 'rgba(255, 255, 255, 0.95)',
                    backdropFilter: 'blur(4px)',
                    boxShadow: 'var(--shadow-xl)',
                    border: '1px solid var(--slate-200)',
                    padding: '12px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    zIndex: 20,
                    pointerEvents: 'none',
                    left: Math.min(getX(hoverIndex) + 16, width - 160) + 'px',
                    top: padding.top + 'px',
                    minWidth: '140px'
                }}>
                    <p style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--slate-700)', borderBottom: '1px solid var(--slate-100)', paddingBottom: '4px' }}>{data[hoverIndex].timestamp}</p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ color: 'var(--slate-500)' }}>Actual:</span>
                        <span style={{ fontWeight: 600, color: 'var(--primary-600)' }}>${(data[hoverIndex].actual || 0).toFixed(4)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--slate-500)' }}>Predicted:</span>
                        <span style={{ fontWeight: 600, color: 'var(--success-600)' }}>${(data[hoverIndex].predicted || 0).toFixed(4)}</span>
                    </div>
                </div>
            )}
        </div>
    );
};

// Helper Components
const Card = ({ children, className = "", style = {}, hover = true }) => (
    <div style={{
        background: 'var(--bg-card)',
        borderRadius: '16px',
        boxShadow: 'var(--shadow-sm)',
        border: '1px solid var(--border-subtle)',
        ...style
    }} className={`${className} ${hover ? 'card-hover' : ''}`}>{children}</div>
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

    if (!stats) return <div style={{ padding: '48px', textAlign: 'center' }}><RefreshCw className="animate-spin" style={{ display: 'inline', color: 'var(--primary-500)', width: '32px', height: '32px' }} /></div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '24px' }}>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <p style={{ color: 'var(--slate-500)', fontSize: '14px', fontWeight: 500 }}>Monthly Savings</p>
                            <h3 style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', letterSpacing: '-0.02em' }}>${stats.totalSavings.toLocaleString()}</h3>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px', fontSize: '12px', color: 'var(--success-600)', background: 'var(--success-50)', width: 'fit-content', padding: '2px 8px', borderRadius: '6px' }}>
                                <TrendingUp style={{ width: '12px', height: '12px' }} /> +12.5%
                            </div>
                        </div>
                        <div style={{ background: 'var(--success-50)', padding: '12px', borderRadius: '12px' }}>
                            <DollarSign style={{ color: 'var(--success-600)', width: '24px', height: '24px' }} />
                        </div>
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <p style={{ color: 'var(--slate-500)', fontSize: '14px', fontWeight: 500 }}>Predictions (24h)</p>
                            <h3 style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', letterSpacing: '-0.02em' }}>{stats.predictionsToday.toLocaleString()}</h3>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px', fontSize: '12px', color: 'var(--primary-600)', background: 'var(--primary-50)', width: 'fit-content', padding: '2px 8px', borderRadius: '6px' }}>
                                <Activity style={{ width: '12px', height: '12px' }} /> 99.9% uptime
                            </div>
                        </div>
                        <div style={{ background: 'var(--primary-50)', padding: '12px', borderRadius: '12px' }}>
                            <Brain style={{ color: 'var(--primary-600)', width: '24px', height: '24px' }} />
                        </div>
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <p style={{ color: 'var(--slate-500)', fontSize: '14px', fontWeight: 500 }}>Active Engines</p>
                            <h3 style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', letterSpacing: '-0.02em' }}>{stats.activeEngines}<span style={{ fontSize: '20px', color: 'var(--slate-400)', fontWeight: 500 }}>/7</span></h3>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px', fontSize: '12px', color: 'var(--warning-600)', background: 'var(--warning-50)', width: 'fit-content', padding: '2px 8px', borderRadius: '6px' }}>
                                <Zap style={{ width: '12px', height: '12px' }} /> High load
                            </div>
                        </div>
                        <div style={{ background: 'var(--warning-50)', padding: '12px', borderRadius: '12px' }}>
                            <Cpu style={{ color: 'var(--warning-600)', width: '24px', height: '24px' }} />
                        </div>
                    </div>
                </Card>
                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <p style={{ color: 'var(--slate-500)', fontSize: '14px', fontWeight: 500 }}>Cluster Health</p>
                            <h3 style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', letterSpacing: '-0.02em' }}>{stats.clusterHealth}%</h3>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px', fontSize: '12px', color: 'var(--danger-600)', background: 'var(--danger-50)', width: 'fit-content', padding: '2px 8px', borderRadius: '6px' }}>
                                <AlertTriangle style={{ width: '12px', height: '12px' }} /> 2 alerts
                            </div>
                        </div>
                        <div style={{ background: 'var(--danger-50)', padding: '12px', borderRadius: '12px' }}>
                            <Activity style={{ color: 'var(--danger-600)', width: '24px', height: '24px' }} />
                        </div>
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
                    <h2 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Live Predictions</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>Real-time inference stream from PricePrediction model</p>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <Badge status="active" />
                    <span style={{ fontSize: '13px', color: 'var(--slate-500)', display: 'flex', alignItems: 'center', gap: '6px', background: 'white', padding: '6px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                        <Activity style={{ width: '16px', height: '16px', color: 'var(--primary-500)' }} /> 45ms latency
                    </span>
                </div>
            </div>

            <Card style={{ padding: '24px' }}>
                <h3 style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '24px', fontSize: '18px' }}>Predicted vs Actual Spot Price (Last 24h)</h3>
                <LineChart data={predictions} height={350} />
            </Card>

            <Card style={{ overflow: 'hidden' }}>
                <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--slate-50)' }}>
                    <h3 style={{ fontWeight: 600, color: 'var(--slate-700)' }}>Recent Inference Logs</h3>
                </div>
                <table style={{ width: '100%', fontSize: '14px', textAlign: 'left', borderCollapse: 'collapse' }}>
                    <thead style={{ background: 'var(--slate-50)', color: 'var(--slate-500)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <tr>
                            <th style={{ padding: '16px 24px', fontWeight: 600 }}>Timestamp</th>
                            <th style={{ padding: '16px 24px', fontWeight: 600 }}>Feature Hash</th>
                            <th style={{ padding: '16px 24px', fontWeight: 600 }}>Predicted</th>
                            <th style={{ padding: '16px 24px', fontWeight: 600 }}>Confidence</th>
                        </tr>
                    </thead>
                    <tbody style={{ borderTop: '1px solid var(--border-subtle)' }}>
                        {predictions.slice(0, 5).map((p, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)', transition: 'background 0.1s' }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--slate-50)'} onMouseLeave={(e) => e.currentTarget.style.background = 'white'}>
                                <td style={{ padding: '16px 24px', fontFamily: 'monospace', color: 'var(--slate-600)' }}>{p.timestamp}</td>
                                <td style={{ padding: '16px 24px', fontFamily: 'monospace', fontSize: '12px', color: 'var(--slate-400)' }}>{p.feature_hash}</td>
                                <td style={{ padding: '16px 24px', fontWeight: 600, color: 'var(--success-600)' }}>${(p.predicted || 0).toFixed(4)}</td>
                                <td style={{ padding: '16px 24px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                        <div style={{ width: '80px', height: '6px', background: 'var(--slate-100)', borderRadius: '9999px', overflow: 'hidden' }}>
                                            <div style={{ height: '100%', background: 'var(--primary-500)', width: `${(p.confidence || 0) * 100}%` }} />
                                        </div>
                                        <span style={{ fontSize: '12px', color: 'var(--slate-500)', fontWeight: 500 }}>{((p.confidence || 0) * 100).toFixed(0)}%</span>
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
                    <h2 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Decision Engines</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>Control autonomous optimization agents</p>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
                {engines.map(engine => (
                    <Card key={engine.id} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative', overflow: 'hidden' }}>
                        <div style={{ position: 'absolute', top: 0, right: 0, padding: '24px' }}>
                            <Badge status={engine.status} />
                        </div>

                        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                            <div style={{
                                padding: '12px',
                                borderRadius: '12px',
                                height: 'fit-content',
                                background: engine.type === 'optimization' ? 'var(--success-50)' : engine.type === 'remediation' ? 'var(--danger-50)' : 'var(--primary-50)',
                                color: engine.type === 'optimization' ? 'var(--success-600)' : engine.type === 'remediation' ? 'var(--danger-600)' : 'var(--primary-600)'
                            }}>
                                {engine.type === 'optimization' ? <DollarSign style={{ width: '24px', height: '24px' }} /> :
                                    engine.type === 'remediation' ? <AlertTriangle style={{ width: '24px', height: '24px' }} /> :
                                        <Search style={{ width: '24px', height: '24px' }} />}
                            </div>
                            <div>
                                <h3 style={{ fontWeight: 700, fontSize: '18px', color: 'var(--text-primary)' }}>{engine.name}</h3>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px', lineHeight: '1.5' }}>{engine.description}</p>
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--slate-500)', fontWeight: 500, background: 'var(--slate-50)', padding: '12px', borderRadius: '8px' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Clock style={{ width: '14px', height: '14px' }} /> Last Run: {engine.lastRun}</span>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Activity style={{ width: '14px', height: '14px' }} /> Impact: {engine.impact}</span>
                        </div>

                        <button
                            onClick={() => toggle(engine.id)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '8px',
                                padding: '10px 16px',
                                borderRadius: '10px',
                                fontWeight: 600,
                                fontSize: '14px',
                                border: 'none',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                background: engine.status === 'active' ? 'var(--slate-100)' : 'var(--primary-600)',
                                color: engine.status === 'active' ? 'var(--slate-600)' : 'white',
                                marginTop: 'auto'
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
                    <h2 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Model Registry</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>Manage lifecycles and retraining pipelines</p>
                </div>
                <button style={{ background: 'var(--primary-600)', color: 'white', padding: '10px 20px', borderRadius: '10px', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', boxShadow: 'var(--shadow-md)', transition: 'transform 0.2s' }} onMouseDown={e => e.currentTarget.style.transform = 'scale(0.98)'} onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}>
                    <Download style={{ width: '18px', height: '18px' }} /> Import Model
                </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                {models.map(model => (
                    <Card key={model.id} style={{ padding: '24px', position: 'relative', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                            <div style={{ padding: '10px', background: 'var(--primary-50)', borderRadius: '10px', color: 'var(--primary-600)' }}>
                                <Layers style={{ width: '24px', height: '24px' }} />
                            </div>
                            <Badge status={model.status} />
                        </div>

                        <h3 style={{ fontWeight: 700, fontSize: '20px', color: 'var(--text-primary)' }}>{model.name}</h3>
                        <p style={{ fontSize: '12px', color: 'var(--slate-500)', fontFamily: 'monospace', marginBottom: '24px', background: 'var(--slate-100)', width: 'fit-content', padding: '2px 6px', borderRadius: '4px' }}>{model.version}</p>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px', marginBottom: '24px', flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--slate-50)' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Framework</span>
                                <span style={{ fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{model.framework}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--slate-50)' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Accuracy</span>
                                <span style={{ fontWeight: 600, color: 'var(--success-600)' }}>{(model.accuracy * 100).toFixed(1)}%</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Last Trained</span>
                                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{model.lastTrained}</span>
                            </div>
                        </div>

                        <button
                            onClick={() => handleRefresh(model.id)}
                            style={{ width: '100%', padding: '10px', border: '1px solid var(--primary-200)', color: 'var(--primary-600)', borderRadius: '10px', fontSize: '14px', fontWeight: 600, background: 'var(--primary-50)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', transition: 'all 0.2s' }}
                            onMouseEnter={e => e.currentTarget.style.background = 'var(--primary-100)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'var(--primary-50)'}
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
                    <h2 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Data Ops: Gap Filler</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>Manage missing data interpolation jobs</p>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                <Card style={{ padding: '24px' }}>
                    <h3 style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: '20px', fontSize: '18px' }}>Start New Gap Analysis</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--slate-500)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Target Dataset</label>
                            <select style={{ width: '100%', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '12px', fontSize: '14px', background: 'var(--bg-app)', color: 'var(--text-primary)', outline: 'none' }}>
                                <option>spot_market_prices</option>
                                <option>node_metrics</option>
                                <option>application_latency</option>
                            </select>
                        </div>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--slate-500)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Fill Strategy</label>
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <button style={{ flex: 1, padding: '10px', background: 'var(--primary-50)', border: '1px solid var(--primary-200)', color: 'var(--primary-700)', borderRadius: '10px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>Interpolation</button>
                                <button style={{ flex: 1, padding: '10px', background: 'white', border: '1px solid var(--border-subtle)', color: 'var(--slate-600)', borderRadius: '10px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>Proxy Fetch</button>
                            </div>
                        </div>
                        <button style={{ width: '100%', background: 'var(--primary-600)', color: 'white', padding: '12px', borderRadius: '10px', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', marginTop: '8px', boxShadow: 'var(--shadow-md)', transition: 'transform 0.2s' }} onMouseDown={e => e.currentTarget.style.transform = 'scale(0.98)'} onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}>
                            Run Analysis
                        </button>
                    </div>
                </Card>

                <Card style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--slate-50)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontWeight: 600, color: 'var(--slate-700)' }}>Recent Jobs</h3>
                        <button style={{ fontSize: '13px', color: 'var(--primary-600)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500 }}>View All</button>
                    </div>
                    <div style={{ flex: 1 }}>
                        {jobs.map(job => (
                            <div key={job.id} style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', transition: 'background 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--slate-50)'} onMouseLeave={(e) => e.currentTarget.style.background = 'white'}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                    <div style={{ padding: '10px', borderRadius: '12px', background: job.status === 'processing' ? 'var(--warning-50)' : 'var(--success-50)', color: job.status === 'processing' ? 'var(--warning-600)' : 'var(--success-600)' }}>
                                        <RefreshCw className={job.status === 'processing' ? 'animate-spin' : ''} style={{ width: '18px', height: '18px' }} />
                                    </div>
                                    <div>
                                        <p style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '14px' }}>{job.dataset}</p>
                                        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>Strategy: {job.strategy} • {job.created_at}</p>
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ display: 'block', fontWeight: 700, color: 'var(--slate-700)', fontSize: '14px' }}>{job.filled_count} pts</span>
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
                    <h2 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Spot Pricing</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>Real-time market data across regions</p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <input type="text" placeholder="Filter by instance type..." style={{ border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '10px 16px', fontSize: '14px', width: '240px', outline: 'none' }} />
                    <button style={{ padding: '10px', border: '1px solid var(--border-subtle)', borderRadius: '10px', background: 'white', cursor: 'pointer', color: 'var(--slate-500)' }}><Filter style={{ width: '18px', height: '18px' }} /></button>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
                {prices.map((p, i) => (
                    <Card key={i} style={{ padding: '20px', transition: 'all 0.2s' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--slate-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{p.region}</span>
                            <span style={{ fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', color: p.trend === 'down' ? 'var(--success-600)' : p.trend === 'up' ? 'var(--danger-600)' : 'var(--slate-500)' }}>
                                {p.trend === 'down' ? <TrendingUp style={{ width: '14px', height: '14px', marginRight: '4px', transform: 'rotate(180deg)' }} /> :
                                    p.trend === 'up' ? <TrendingUp style={{ width: '14px', height: '14px', marginRight: '4px' }} /> : null}
                                {p.trend}
                            </span>
                        </div>
                        <h3 style={{ fontWeight: 700, fontSize: '20px', color: 'var(--text-primary)' }}>{p.instanceType}</h3>
                        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>{p.az}</p>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                            <span style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>${p.price}</span>
                            <span style={{ fontSize: '13px', color: 'var(--slate-400)' }}>/hr</span>
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
            padding: '12px 16px',
            borderRadius: '12px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            cursor: 'pointer',
            background: active ? 'var(--primary-50)' : 'transparent',
            color: active ? 'var(--primary-700)' : 'var(--slate-600)',
            transition: 'all 0.2s',
            position: 'relative'
        }}
        onMouseEnter={(e) => !active && (e.currentTarget.style.background = 'var(--slate-50)')}
        onMouseLeave={(e) => !active && (e.currentTarget.style.background = 'transparent')}
    >
        {active && <div style={{ position: 'absolute', left: 0, top: '10%', height: '80%', width: '4px', background: 'var(--primary-600)', borderRadius: '0 4px 4px 0' }} />}
        <Icon style={{ width: '20px', height: '20px', color: active ? 'var(--primary-600)' : 'var(--slate-400)' }} />
        {label}
    </button>
);

const App = () => {
    const [view, setView] = useState('overview');

    return (
        <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', fontFamily: 'system-ui, -apple-system, sans-serif', color: '#0f172a' }}>
            {/* Sidebar */}
            <aside style={{ width: '280px', background: 'var(--bg-card)', borderRight: '1px solid var(--border-subtle)', position: 'fixed', height: '100%', zIndex: 20, display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-lg)' }}>
                <div style={{ height: '80px', display: 'flex', alignItems: 'center', padding: '0 32px' }}>
                    <div style={{ width: '40px', height: '40px', background: 'linear-gradient(135deg, var(--primary-600), var(--primary-500))', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '16px', boxShadow: 'var(--shadow-glow)' }}>
                        <Server style={{ width: '24px', height: '24px', color: 'white' }} />
                    </div>
                    <div>
                        <span style={{ fontWeight: 700, fontSize: '20px', letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>CloudOptim</span>
                        <span style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>ML Server</span>
                    </div>
                </div>

                <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflowY: 'auto' }}>
                    <p style={{ padding: '0 16px', fontSize: '11px', fontWeight: 700, color: 'var(--slate-400)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', marginTop: '8px' }}>Core Platform</p>
                    <SidebarLink icon={LayoutDashboard} label="Overview" active={view === 'overview'} onClick={() => setView('overview')} />
                    <SidebarLink icon={Zap} label="Live Predictions" active={view === 'predictions'} onClick={() => setView('predictions')} />
                    <SidebarLink icon={Cpu} label="Decision Engines" active={view === 'engines'} onClick={() => setView('engines')} />

                    <p style={{ padding: '0 16px', fontSize: '11px', fontWeight: 700, color: 'var(--slate-400)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', marginTop: '32px' }}>ML Operations</p>
                    <SidebarLink icon={Layers} label="Model Registry" active={view === 'models'} onClick={() => setView('models')} />
                    <SidebarLink icon={Database} label="Data Gap Filler" active={view === 'data'} onClick={() => setView('data')} />
                    <SidebarLink icon={DollarSign} label="Pricing Data" active={view === 'pricing'} onClick={() => setView('pricing')} />
                </div>

                <div style={{ padding: '24px', borderTop: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', borderRadius: '12px', cursor: 'pointer', transition: 'background 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--slate-50)'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                        <div style={{ width: '40px', height: '40px', background: 'linear-gradient(135deg, var(--primary-100), var(--primary-200))', color: 'var(--primary-700)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '16px' }}>A</div>
                        <div>
                            <p style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Admin User</p>
                            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>admin@mlserver.io</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, marginLeft: '280px', display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-app)' }}>
                <header style={{ height: '80px', background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border-subtle)', position: 'sticky', top: 0, zIndex: 10, padding: '0 40px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '14px', color: 'var(--slate-500)', background: 'var(--slate-50)', padding: '6px 16px', borderRadius: '9999px', border: '1px solid var(--border-subtle)' }}>
                        <GitBranch style={{ width: '16px', height: '16px' }} />
                        Branch: <span style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--slate-700)' }}>main</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--success-700)', background: 'var(--success-50)', padding: '6px 12px', borderRadius: '9999px', border: '1px solid var(--success-100)' }}>
                            <div className="animate-pulse" style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--success-500)' }} />
                            System Online
                        </div>
                        <button style={{ padding: '10px', borderRadius: '12px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--slate-400)', transition: 'all 0.2s' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--slate-100)'; e.currentTarget.style.color = 'var(--slate-600)'; }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--slate-400)'; }}>
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
