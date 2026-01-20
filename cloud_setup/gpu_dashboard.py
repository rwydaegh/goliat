"""
TensorDock GPU Dashboard v3
===========================
Full-featured dashboard with GPU browsing, VM deployment, and instance management.
Run this script and open http://localhost:8080 in your browser.
"""

import http.server
import json
import os
import requests
import threading
import time
from urllib.parse import urlparse

API_TOKEN = "08OqRwTex93OHk9YTbojyj4PComoWLNU"
BASE_URL = "https://dashboard.tensordock.com/api/v2"

# Cache for API data - show old data instantly while fetching new
_cache = {"data": None, "timestamp": 0, "fetching": False}
CACHE_TTL = 300  # 5 minutes

# Availability cache - persisted to file
AVAILABILITY_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "availability_cache.json")
_availability_cache = {}  # Key: locationId_gpuV0Name, Value: {"available": bool, "timestamp": float, "reason": str}


def _load_availability_cache():
    """Load availability cache from file."""
    global _availability_cache
    try:
        if os.path.exists(AVAILABILITY_CACHE_FILE):
            with open(AVAILABILITY_CACHE_FILE, "r") as f:
                _availability_cache = json.load(f)
            print(f"[Availability] Loaded {len(_availability_cache)} cached results")
    except Exception as e:
        print(f"[Availability] Failed to load cache: {e}")
        _availability_cache = {}


def _save_availability_cache():
    """Save availability cache to file."""
    try:
        with open(AVAILABILITY_CACHE_FILE, "w") as f:
            json.dump(_availability_cache, f, indent=2)
    except Exception as e:
        print(f"[Availability] Failed to save cache: {e}")


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TensorDock GPU Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --bg-card-hover: #222230;
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border-color: #2a2a3a;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }

        .container { max-width: 1800px; margin: 0 auto; padding: 1.5rem; }

        header {
            text-align: center;
            margin-bottom: 2rem;
            padding: 1.5rem;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-radius: 16px;
            border: 1px solid var(--border-color);
        }

        h1 {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.25rem;
        }

        .subtitle { color: var(--text-secondary); font-size: 0.95rem; }

        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }

        .stat { text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: 700; color: var(--accent-primary); }
        .stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

        /* Controls Bar */
        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            align-items: center;
        }

        .search-box {
            flex: 1;
            min-width: 250px;
            position: relative;
        }

        .search-input {
            width: 100%;
            padding: 0.75rem 1rem 0.75rem 2.75rem;
            border: 1px solid var(--border-color);
            background: var(--bg-card);
            color: var(--text-primary);
            border-radius: 10px;
            font-size: 0.9rem;
            transition: all 0.2s;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        .search-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }

        .control-group {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }

        .control-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            white-space: nowrap;
        }

        select, .btn {
            padding: 0.65rem 1rem;
            border: 1px solid var(--border-color);
            background: var(--bg-card);
            color: var(--text-primary);
            border-radius: 8px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        select:hover, .btn:hover {
            border-color: var(--accent-primary);
            background: var(--bg-card-hover);
        }

        .btn-primary {
            background: var(--accent-primary);
            border-color: var(--accent-primary);
            color: white;
        }

        .btn-primary:hover {
            background: #5558e3;
        }

        /* Filters */
        .filters {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 0.5rem 1rem;
            border: 1px solid var(--border-color);
            background: var(--bg-card);
            color: var(--text-secondary);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .filter-btn:hover, .filter-btn.active {
            background: var(--accent-primary);
            color: white;
            border-color: var(--accent-primary);
        }

        .filter-btn.sim4life {
            background: linear-gradient(135deg, #06b6d4, #0891b2);
            border-color: #06b6d4;
            color: white;
        }

        /* View Toggle */
        .view-toggle {
            display: flex;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }

        .view-btn {
            padding: 0.5rem 1rem;
            background: var(--bg-card);
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.85rem;
        }

        .view-btn.active {
            background: var(--accent-primary);
            color: white;
        }

        /* GPU Grid */
        .gpu-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 1rem;
        }

        .gpu-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .gpu-card:hover {
            background: var(--bg-card-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .gpu-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        }

        .gpu-card.has-ip::before {
            background: linear-gradient(90deg, var(--accent-green), #34d399);
        }

        .gpu-card.sim4life-pick::before {
            background: linear-gradient(90deg, var(--accent-cyan), #0891b2);
        }

        .sim4life-badge {
            position: absolute;
            top: 8px;
            right: 8px;
            background: linear-gradient(135deg, #06b6d4, #0891b2);
            color: white;
            font-size: 0.65rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: 600;
        }

        .gpu-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
            padding-right: 60px;
        }

        .gpu-name {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .gpu-tier {
            font-size: 0.65rem;
            padding: 0.2rem 0.5rem;
            border-radius: 12px;
            font-weight: 500;
        }

        .tier-flagship { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; }
        .tier-datacenter { background: linear-gradient(135deg, #8b5cf6, #6366f1); color: #fff; }
        .tier-professional { background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; }
        .tier-consumer { background: linear-gradient(135deg, #10b981, #059669); color: #fff; }
        .tier-mid { background: var(--bg-secondary); color: var(--text-secondary); }

        .gpu-location {
            color: var(--text-secondary);
            font-size: 0.8rem;
            margin-bottom: 0.75rem;
        }

        .gpu-price {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent-green);
            margin-bottom: 0.5rem;
        }

        .gpu-price span {
            font-size: 0.75rem;
            font-weight: 400;
            color: var(--text-muted);
        }

        .gpu-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }

        .gpu-stat {
            background: var(--bg-secondary);
            padding: 0.5rem;
            border-radius: 6px;
            text-align: center;
        }

        .gpu-stat-label {
            font-size: 0.6rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .gpu-stat-value {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .gpu-features {
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
            margin-bottom: 0.5rem;
        }

        .feature-badge {
            font-size: 0.65rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-weight: 500;
        }

        .feature-ip { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
        .feature-port { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }
        .feature-storage { background: rgba(139, 92, 246, 0.15); color: var(--accent-secondary); }
        .feature-multi { background: rgba(245, 158, 11, 0.15); color: var(--accent-yellow); }

        .gpu-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }

        .gpu-actions .btn {
            flex: 1;
            padding: 0.5rem;
            font-size: 0.75rem;
            text-align: center;
        }

        .location-id {
            font-size: 0.6rem;
            color: var(--text-muted);
            font-family: 'Monaco', 'Menlo', monospace;
            margin-top: 0.5rem;
            padding: 0.35rem;
            background: var(--bg-secondary);
            border-radius: 4px;
            word-break: break-all;
        }

        /* Table View */
        .gpu-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }

        .gpu-table th {
            background: var(--bg-card);
            padding: 0.75rem;
            text-align: left;
            border-bottom: 2px solid var(--border-color);
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            white-space: nowrap;
        }

        .gpu-table th:hover {
            color: var(--accent-primary);
        }

        .gpu-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }

        .gpu-table tr:hover {
            background: var(--bg-card);
        }

        .gpu-table .feature-badges {
            display: flex;
            gap: 0.25rem;
        }

        /* Cost Calculator Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }

        .modal h2 {
            margin-bottom: 1.5rem;
            font-size: 1.25rem;
        }

        .modal-close {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }

        .form-group input, .form-group select {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            border-radius: 8px;
            font-size: 0.9rem;
        }

        .cost-result {
            background: linear-gradient(135deg, var(--bg-secondary), var(--bg-card));
            padding: 1.5rem;
            border-radius: 12px;
            margin-top: 1rem;
            text-align: center;
        }

        .cost-total {
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-green);
        }

        .cost-breakdown {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: var(--bg-card);
            border: 1px solid var(--accent-green);
            color: var(--text-primary);
            padding: 1rem 2rem;
            border-radius: 10px;
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1001;
        }

        .toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }

        /* Refresh */
        .refresh-btn {
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            padding: 0.75rem 1.25rem;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            color: white;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.85rem;
            box-shadow: 0 10px 30px rgba(99, 102, 241, 0.3);
            transition: all 0.3s ease;
        }

        .refresh-btn:hover {
            transform: scale(1.05);
        }

        .auto-refresh-indicator {
            position: fixed;
            bottom: 4rem;
            right: 1.5rem;
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        .loading {
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
        }

        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        /* Navigation Tabs */
        .nav-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; }
        .nav-tab { padding: 0.75rem 1.5rem; background: transparent; border: none; color: var(--text-secondary); cursor: pointer; font-size: 0.9rem; font-weight: 500; border-radius: 8px 8px 0 0; transition: all 0.2s; }
        .nav-tab:hover { color: var(--text-primary); background: var(--bg-card); }
        .nav-tab.active { color: var(--accent-primary); background: var(--bg-card); border-bottom: 2px solid var(--accent-primary); }

        /* Instance Cards */
        .instance-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
        .instance-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .instance-name { font-size: 1.1rem; font-weight: 600; }
        .status-badge { padding: 0.35rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
        .status-running { background: rgba(16,185,129,0.2); color: var(--accent-green); }
        .status-stopped { background: rgba(239,68,68,0.2); color: var(--accent-red); }
        .status-starting { background: rgba(245,158,11,0.2); color: var(--accent-yellow); }
        .instance-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
        .detail-group { background: var(--bg-secondary); padding: 1rem; border-radius: 8px; }
        .detail-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.25rem; }
        .detail-value { font-size: 0.9rem; font-weight: 500; }
        .instance-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

        .btn-success { background: var(--accent-green); border-color: var(--accent-green); color: white; }
        .btn-danger { background: var(--accent-red); border-color: var(--accent-red); color: white; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .empty-state { text-align: center; padding: 4rem 2rem; color: var(--text-secondary); }
        .empty-state h3 { font-size: 1.25rem; margin-bottom: 0.5rem; color: var(--text-primary); }

        .password-hint { font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem; }
        .password-valid { color: var(--accent-green); }
        .password-invalid { color: var(--accent-red); }

        .toast.error { border-color: var(--accent-red); }

        .gpu-card.unavailable { opacity: 0.4; position: relative; }
        .gpu-card.unavailable::after { content: '❌ Unavailable'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(239,68,68,0.9); color: white; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; z-index: 10; }
        .gpu-card.testing { opacity: 0.7; }
        .gpu-card.testing::after { content: '🔄 Testing...'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(245,158,11,0.9); color: white; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; z-index: 10; }
        .gpu-card.available::after { content: '✅ Available'; position: absolute; top: 0.5rem; right: 0.5rem; background: rgba(16,185,129,0.9); color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; z-index: 10; }

        footer {
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            color: var(--text-muted);
            font-size: 0.8rem;
        }

        @media (max-width: 768px) {
            .container { padding: 1rem; }
            h1 { font-size: 1.5rem; }
            .gpu-grid { grid-template-columns: 1fr; }
            .controls { flex-direction: column; }
            .search-box { min-width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 TensorDock GPU Dashboard</h1>
            <p class="subtitle">Browse GPUs • Deploy VMs • Manage Instances</p>
            <div class="stats-bar" id="stats-bar">
                <div class="loading"><div class="loading-spinner"></div></div>
            </div>
        </header>

        <div class="nav-tabs">
            <button class="nav-tab active" data-tab="gpus">🎮 Available GPUs</button>
            <button class="nav-tab" data-tab="instances">📋 My Instances</button>
        </div>

        <!-- GPU Tab -->
        <div id="gpus-tab">
            <!-- Controls -->
            <div class="controls">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" class="search-input" id="search" placeholder="Search GPUs (e.g., 4090, H100, A6000...)">
                </div>

                <div class="control-group">
                    <span class="control-label">Sort:</span>
                    <select id="sort">
                        <option value="tier">GPU Tier</option>
                        <option value="price-asc">Price: Low → High</option>
                        <option value="price-desc">Price: High → Low</option>
                        <option value="vcpus">Max vCPUs</option>
                        <option value="ram">Max RAM</option>
                        <option value="gpus">Max GPUs</option>
                    </select>
                </div>

                <div class="control-group">
                    <span class="control-label">View:</span>
                    <div class="view-toggle">
                        <button class="view-btn active" data-view="cards">Cards</button>
                        <button class="view-btn" data-view="table">Table</button>
                    </div>
                </div>

                <div class="control-group">
                    <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                        <input type="checkbox" id="auto-refresh">
                        <span class="control-label">Auto-refresh</span>
                    </label>
                </div>
            </div>

            <!-- Filters -->
            <div class="filters" id="filters">
                <button class="filter-btn active" data-filter="all">All GPUs</button>
                <button class="filter-btn" data-filter="multi-gpu">🔥 Multi-GPU (2+)</button>
                <button class="filter-btn" data-filter="flagship">💎 Flagship</button>
                <button class="filter-btn" data-filter="budget">💰 Under $0.35/hr</button>
                <button class="filter-btn" id="test-availability-btn" onclick="testAllAvailability()" style="background: linear-gradient(135deg, #f59e0b, #d97706); margin-left: auto;">🧪 Test All Availability</button>
            </div>

            <div id="content">
                <div class="loading"><div class="loading-spinner"></div>Fetching GPU availability...</div>
            </div>
        </div>

        <!-- Instances Tab -->
        <div id="instances-tab" style="display:none;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
                <h2 style="font-size:1.25rem;">Your Instances</h2>
                <button class="btn btn-primary" onclick="loadInstances()">🔄 Refresh</button>
            </div>
            <div id="instances-content"><div class="loading"><div class="loading-spinner"></div>Loading instances...</div></div>
        </div>

        <footer>
            <div id="cache-status" style="margin-bottom: 0.5rem; padding: 0.5rem; background: var(--bg-card); border-radius: 8px; display: inline-block;">
                📡 <span id="data-status">Loading...</span>
            </div>
            <br>
            <a href="#" onclick="openCostCalculator(); return false;" style="color: var(--accent-primary);">💰 Cost Calculator</a>
        </footer>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄 Refresh</button>
    <div class="auto-refresh-indicator" id="auto-refresh-indicator" style="display: none;">Auto-refresh: <span id="countdown">30</span>s</div>

    <!-- Cost Calculator Modal -->
    <div class="modal-overlay" id="cost-modal">
        <div class="modal">
            <h2>💰 Cost Calculator</h2>
            <div class="form-group">
                <label>Select GPU</label>
                <select id="calc-gpu"></select>
            </div>
            <div class="form-group">
                <label>Number of GPUs</label>
                <input type="number" id="calc-gpu-count" value="1" min="1" max="8">
            </div>
            <div class="form-group">
                <label>vCPUs</label>
                <input type="number" id="calc-vcpus" value="8" min="1">
            </div>
            <div class="form-group">
                <label>RAM (GB)</label>
                <input type="number" id="calc-ram" value="32" min="1">
            </div>
            <div class="form-group">
                <label>Storage (GB)</label>
                <input type="number" id="calc-storage" value="250" min="100">
            </div>
            <div class="form-group">
                <label>Hours per day</label>
                <input type="number" id="calc-hours" value="8" min="1" max="24">
            </div>
            <div class="form-group">
                <label>Location</label>
                <select id="calc-location"></select>
            </div>
            <div class="form-group">
                <label>Password (for Windows RDP)</label>
                <input type="text" id="calc-password" placeholder="MySecurePass123!@">
                <div class="password-hint" id="password-hint">Min 10 chars, 1 uppercase, 1 number, 1 symbol</div>
            </div>
            <div class="cost-result" id="cost-result">
                <div class="cost-total">$0.00</div>
                <div class="cost-breakdown">Configure resources to see estimate</div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                <button class="btn" onclick="closeCostCalculator()">Close</button>
                <button class="btn" onclick="copyDeploymentJson()">📋 Copy JSON</button>
                <button class="btn btn-success" id="deploy-btn" onclick="deployVM()">🚀 Deploy Now</button>
            </div>
        </div>
    </div>

    <div class="toast" id="toast">Copied to clipboard!</div>

    <script>
        let allData = [];
        let currentView = 'cards';
        let currentFilter = 'all';
        let currentSort = 'tier';
        let searchQuery = '';
        let autoRefreshInterval = null;
        let availabilityState = {};  // Key: locationId_gpuV0Name, Value: true/false/null (tested/not tested)

        // Prettify GPU names from API format to readable format
        function formatGpuName(v0Name, displayName) {
            // Helper to keep only last 3 words
            const trimToLast3 = (str) => str.split(' ').slice(-3).join(' ');

            // If displayName looks good (has NVIDIA in it), use it but trim
            if (displayName && displayName.includes('NVIDIA')) {
                return trimToLast3(displayName);
            }

            // Parse the v0Name format like "a40-pcie-48gb" or "geforcertx4090-pcie-24gb"
            let name = v0Name.toLowerCase();

            // GPU name mappings for known models
            const gpuPatterns = [
                // Flagship datacenter
                { pattern: /h100[- ]?sxm5?[- ]?(\d+)gb/i, name: 'NVIDIA H100 SXM5', vram: '$1GB' },
                { pattern: /h100[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA H100 PCIe', vram: '$1GB' },
                { pattern: /h200/i, name: 'NVIDIA H200', vram: '' },
                { pattern: /a100[- ]?sxm4?[- ]?(\d+)gb/i, name: 'NVIDIA A100 SXM4', vram: '$1GB' },
                { pattern: /a100[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA A100 PCIe', vram: '$1GB' },

                // Professional
                { pattern: /l40s?[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA L40S PCIe', vram: '$1GB' },
                { pattern: /l40[- ]?(\d+)gb/i, name: 'NVIDIA L40', vram: '$1GB' },
                { pattern: /rtxa6000[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA RTX A6000 PCIe', vram: '$1GB' },
                { pattern: /a6000[- ]?(\d+)gb/i, name: 'NVIDIA RTX A6000', vram: '$1GB' },
                { pattern: /rtx[- ]?6000[- ]?ada[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA RTX 6000 ADA PCIe', vram: '$1GB' },
                { pattern: /rtxa5000[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA RTX A5000 PCIe', vram: '$1GB' },
                { pattern: /a5000[- ]?(\d+)gb/i, name: 'NVIDIA RTX A5000', vram: '$1GB' },
                { pattern: /rtxa4500[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA RTX A4500 PCIe', vram: '$1GB' },
                { pattern: /a4500[- ]?(\d+)gb/i, name: 'NVIDIA RTX A4500', vram: '$1GB' },
                { pattern: /rtxa4000[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA RTX A4000 PCIe', vram: '$1GB' },
                { pattern: /a4000[- ]?(\d+)gb/i, name: 'NVIDIA RTX A4000', vram: '$1GB' },
                { pattern: /a40[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA A40 PCIe', vram: '$1GB' },
                { pattern: /^a40[- ]?(\d+)gb/i, name: 'NVIDIA A40', vram: '$1GB' },

                // Consumer - GeForce RTX 50 series
                { pattern: /geforce[- ]?rtx[- ]?5090[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 5090 PCIe', vram: '$1GB' },
                { pattern: /rtx[- ]?5090[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 5090', vram: '$1GB' },

                // Consumer - GeForce RTX 40 series
                { pattern: /geforce[- ]?rtx[- ]?4090[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4090 PCIe', vram: '$1GB' },
                { pattern: /rtx[- ]?4090[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4090', vram: '$1GB' },
                { pattern: /geforce[- ]?rtx[- ]?4080[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4080 PCIe', vram: '$1GB' },
                { pattern: /rtx[- ]?4080[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4080', vram: '$1GB' },
                { pattern: /geforce[- ]?rtx[- ]?4070[- ]?ti[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4070 Ti', vram: '$1GB' },
                { pattern: /geforce[- ]?rtx[- ]?4070[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 4070', vram: '$1GB' },

                // Consumer - GeForce RTX 30 series
                { pattern: /geforce[- ]?rtx[- ]?3090[- ]?ti[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 3090 Ti', vram: '$1GB' },
                { pattern: /geforce[- ]?rtx[- ]?3090[- ]?pcie[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 3090 PCIe', vram: '$1GB' },
                { pattern: /rtx[- ]?3090[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 3090', vram: '$1GB' },
                { pattern: /geforce[- ]?rtx[- ]?3080[- ]?ti[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 3080 Ti', vram: '$1GB' },
                { pattern: /rtx[- ]?3080[- ]?(\d+)gb/i, name: 'NVIDIA GeForce RTX 3080', vram: '$1GB' },

                // Tesla / Datacenter older
                { pattern: /tesla[- ]?v100[- ]?sxm2[- ]?(\d+)gb/i, name: 'NVIDIA Tesla V100 SXM2', vram: '$1GB' },
                { pattern: /tesla[- ]?v100[- ]?sxm3[- ]?(\d+)gb/i, name: 'NVIDIA Tesla V100 SXM3', vram: '$1GB' },
                { pattern: /v100[- ]?sxm2[- ]?(\d+)gb/i, name: 'NVIDIA Tesla V100 SXM2', vram: '$1GB' },
                { pattern: /v100[- ]?sxm3[- ]?(\d+)gb/i, name: 'NVIDIA Tesla V100 SXM3', vram: '$1GB' },
                { pattern: /v100[- ]?(\d+)gb/i, name: 'NVIDIA Tesla V100', vram: '$1GB' },
                { pattern: /tesla[- ]?t4[- ]?(\d+)gb/i, name: 'NVIDIA Tesla T4', vram: '$1GB' },
                { pattern: /t4[- ]?(\d+)gb/i, name: 'NVIDIA T4', vram: '$1GB' },
            ];

            for (const { pattern, name: gpuName, vram } of gpuPatterns) {
                if (pattern.test(v0Name)) {
                    const vramMatch = v0Name.match(pattern);
                    if (vramMatch && vram) {
                        return trimToLast3(gpuName + ' ' + vram.replace('$1', vramMatch[1]));
                    }
                    return trimToLast3(gpuName);
                }
            }

            // Fallback: capitalize and clean up the name, then trim to last 3 words
            const formatted = v0Name
                .replace(/-/g, ' ')
                .replace(/pcie/gi, 'PCIe')
                .replace(/sxm(\d)/gi, 'SXM$1')
                .replace(/(\d+)gb/gi, '$1GB')
                .replace(/geforce/gi, 'GeForce')
                .replace(/rtx/gi, 'RTX')
                .replace(/nvidia/gi, 'NVIDIA')
                .replace(/tesla/gi, 'Tesla')
                .split(' ')
                .map(word => {
                    if (['PCIe', 'SXM', 'SXM2', 'SXM3', 'SXM4', 'SXM5', 'RTX', 'NVIDIA', 'GeForce', 'Tesla'].includes(word)) return word;
                    if (/^\d+GB$/i.test(word)) return word.toUpperCase();
                    if (/^[a-z]\d+$/i.test(word)) return word.toUpperCase(); // A100, H100, etc
                    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
                })
                .join(' ');
            return trimToLast3(formatted);
        }

        function getGpuTier(gpuName) {
            const name = gpuName.toLowerCase();
            if (name.includes('h100') || name.includes('h200')) return { tier: 'flagship', label: 'Flagship', priority: 1 };
            if (name.includes('a100')) return { tier: 'datacenter', label: 'Datacenter', priority: 2 };
            if (name.includes('l40') || name.includes('a6000') || name.includes('6000')) return { tier: 'professional', label: 'Professional', priority: 3 };
            if (name.includes('5090') || name.includes('4090')) return { tier: 'consumer', label: 'Consumer Top', priority: 4 };
            if (name.includes('3090') || name.includes('4080')) return { tier: 'consumer', label: 'Consumer High', priority: 5 };
            if (name.includes('a5000') || name.includes('a4000') || name.includes('l4')) return { tier: 'professional', label: 'Pro Mid', priority: 6 };
            if (name.includes('4070') || name.includes('3080') || name.includes('a4500')) return { tier: 'mid', label: 'Mid-Range', priority: 7 };
            return { tier: 'mid', label: 'Mid-Range', priority: 10 };
        }

        async function loadData() {
            const contentEl = document.getElementById('content');
            const startTime = Date.now();

            // Show loading with elapsed timer
            let loadingInterval;
            const showLoading = () => {
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                contentEl.innerHTML = `<div class="loading"><div class="loading-spinner"></div>Fetching GPU availability... (${elapsed}s)</div>`;
            };
            showLoading();
            loadingInterval = setInterval(showLoading, 100);

            try {
                // Add 15 second timeout
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 15000);

                const response = await fetch('/api/data', { signal: controller.signal });
                clearTimeout(timeoutId);
                clearInterval(loadingInterval);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.error) {
                    throw new Error(data.error);
                }

                allData = data.locations || [];

                if (allData.length === 0) {
                    contentEl.innerHTML = `<div class="loading" style="color: var(--accent-yellow);">No GPU data returned. <button class="btn" onclick="loadData()">🔄 Retry</button></div>`;
                    return;
                }

                renderData();
                updateStats();
                updateCalcDropdown();
                updateLocationDropdown();

                // Show clear cache status
                const isCached = data._cached === true;
                const cacheAge = data._cache_age || 0;
                const now = new Date();
                const statusEl = document.getElementById('data-status');

                if (isCached) {
                    statusEl.innerHTML = `<span style="color: var(--accent-yellow);">📦 CACHED DATA</span> • Age: ${cacheAge}s • Displayed at: ${now.toLocaleTimeString()} • <em>Click Refresh for fresh data</em>`;
                } else {
                    statusEl.innerHTML = `<span style="color: var(--accent-green);">✅ FRESH DATA</span> • Fetched now from TensorDock API • ${now.toLocaleTimeString()}`;
                }

            } catch (err) {
                clearInterval(loadingInterval);
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

                let errorMsg = err.message;
                if (err.name === 'AbortError') {
                    errorMsg = 'Request timed out after 15 seconds';
                }

                contentEl.innerHTML = `
                    <div class="loading" style="color: var(--accent-red);">
                        ❌ Error after ${elapsed}s: ${errorMsg}<br><br>
                        <button class="btn btn-primary" onclick="loadData()">🔄 Retry</button>
                    </div>
                `;
            }
        }

        // Load availability cache from server
        async function loadAvailabilityCache() {
            try {
                const resp = await fetch('/api/availability');
                if (resp.ok) {
                    const data = await resp.json();
                    // Convert server format {key: {available: bool, timestamp: x}} to simple {key: bool}
                    for (const [key, value] of Object.entries(data)) {
                        availabilityState[key] = value.available;
                    }
                    console.log(`[Availability] Loaded ${Object.keys(availabilityState).length} cached results`);
                }
            } catch (e) {
                console.log('[Availability] Failed to load cache:', e);
            }
        }

        function updateStats() {
            let totalGpus = 0, gpuTypes = new Set(), dedicatedIpCount = 0;

            allData.forEach(loc => {
                loc.gpus.forEach(gpu => {
                    totalGpus += gpu.max_count;
                    gpuTypes.add(gpu.v0Name);
                    if (gpu.network_features?.dedicated_ip_available) dedicatedIpCount++;
                });
            });

            document.getElementById('stats-bar').innerHTML = `
                <div class="stat"><div class="stat-value">${totalGpus}</div><div class="stat-label">Total GPUs</div></div>
                <div class="stat"><div class="stat-value">${gpuTypes.size}</div><div class="stat-label">GPU Types</div></div>
                <div class="stat"><div class="stat-value">${allData.length}</div><div class="stat-label">Locations</div></div>
                <div class="stat"><div class="stat-value">${dedicatedIpCount}</div><div class="stat-label">Dedicated IP</div></div>
            `;
        }

        function prepareCards() {
            let cards = [];

            allData.forEach(loc => {
                loc.gpus.forEach(gpu => {
                    const tier = getGpuTier(gpu.v0Name);
                    const hasIp = gpu.network_features?.dedicated_ip_available;
                    const hasPort = gpu.network_features?.port_forwarding_available;
                    const hasStorage = gpu.network_features?.network_storage_available;
                    const isMultiGpu = gpu.max_count >= 2;

                    // Apply filters
                    if (currentFilter === 'dedicated-ip' && !hasIp) return;
                    if (currentFilter === 'multi-gpu' && !isMultiGpu) return;
                    if (currentFilter === 'flagship' && tier.priority > 3) return;
                    if (currentFilter === 'budget' && gpu.price_per_hr > 0.35) return;

                    // Apply search
                    if (searchQuery) {
                        const q = searchQuery.toLowerCase();
                        const searchable = `${gpu.v0Name} ${gpu.displayName} ${loc.city} ${loc.country}`.toLowerCase();
                        if (!searchable.includes(q)) return;
                    }

                    cards.push({ gpu, location: loc, tier, hasIp, hasPort, hasStorage, isMultiGpu });
                });
            });

            // Sort
            cards.sort((a, b) => {
                switch (currentSort) {
                    case 'price-asc': return a.gpu.price_per_hr - b.gpu.price_per_hr;
                    case 'price-desc': return b.gpu.price_per_hr - a.gpu.price_per_hr;
                    case 'vcpus': return (b.gpu.resources?.max_vcpus || 0) - (a.gpu.resources?.max_vcpus || 0);
                    case 'ram': return (b.gpu.resources?.max_ram_gb || 0) - (a.gpu.resources?.max_ram_gb || 0);
                    case 'gpus': return b.gpu.max_count - a.gpu.max_count;
                    default: // tier
                        if (a.tier.priority !== b.tier.priority) return a.tier.priority - b.tier.priority;
                        return a.gpu.price_per_hr - b.gpu.price_per_hr;
                }
            });

            return cards;
        }

        function renderData() {
            const cards = prepareCards();

            if (cards.length === 0) {
                document.getElementById('content').innerHTML = '<div class="loading">No GPUs match the criteria.</div>';
                return;
            }

            if (currentView === 'table') {
                renderTable(cards);
            } else {
                renderCards(cards);
            }
        }

        function renderCards(cards) {
            let html = '<div class="gpu-grid">';

            cards.forEach(({ gpu, location, tier, hasIp, hasPort, hasStorage, isMultiGpu }) => {
                const resources = gpu.resources || {};
                const cardClass = hasIp ? 'has-ip' : '';

                html += `
                    <div class="gpu-card ${cardClass}" data-location-id="${location.id}" data-gpu-name="${gpu.v0Name}">
                        <div class="gpu-header">
                            <h3 class="gpu-name">${formatGpuName(gpu.v0Name, gpu.displayName)}</h3>
                        </div>
                        <div class="gpu-location">📍 ${location.city}, ${location.stateprovince}, ${location.country}</div>
                        <div class="gpu-price">$${gpu.price_per_hr.toFixed(2)} <span>/hr per GPU</span></div>
                        <div class="gpu-stats">
                            <div class="gpu-stat"><div class="gpu-stat-label">GPUs</div><div class="gpu-stat-value">${gpu.max_count}x</div></div>
                            <div class="gpu-stat"><div class="gpu-stat-label">vCPUs</div><div class="gpu-stat-value">${resources.max_vcpus || '?'}</div></div>
                            <div class="gpu-stat"><div class="gpu-stat-label">RAM</div><div class="gpu-stat-value">${resources.max_ram_gb || '?'} GB</div></div>
                            <div class="gpu-stat"><div class="gpu-stat-label">Storage</div><div class="gpu-stat-value">${resources.max_storage_gb || '?'} GB</div></div>
                        </div>
                        <div class="gpu-features">
                            ${hasIp ? '<span class="feature-badge feature-ip">🌐 Dedicated IP</span>' : ''}
                            ${hasPort ? '<span class="feature-badge feature-port">🔌 Port Forward</span>' : ''}
                            ${hasStorage ? '<span class="feature-badge feature-storage">💾 Net Storage</span>' : ''}
                            ${isMultiGpu ? '<span class="feature-badge feature-multi">🔥 Multi-GPU</span>' : ''}
                        </div>
                        <div class="gpu-actions">
                            <button class="btn" onclick="copyLocationId('${location.id}')">📋 Copy ID</button>
                            <button class="btn btn-primary" onclick="openCostCalculatorFor('${gpu.v0Name}', '${location.id}')">💰 Calculate</button>
                        </div>
                        <div class="location-id">${location.id}</div>
                    </div>
                `;
            });

            html += '</div>';
            document.getElementById('content').innerHTML = html;
        }

        function renderTable(cards) {
            let html = `
                <table class="gpu-table">
                    <thead>
                        <tr>
                            <th>GPU</th>
                            <th>Location</th>
                            <th>Price/hr</th>
                            <th>Max GPUs</th>
                            <th>Max vCPUs</th>
                            <th>Max RAM</th>
                            <th>Storage</th>
                            <th>Features</th>
                            <th>Available</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            cards.forEach(({ gpu, location, tier, hasIp, hasPort, hasStorage, isMultiGpu }) => {
                const resources = gpu.resources || {};
                html += `
                    <tr>
                        <td>
                            <strong>${formatGpuName(gpu.v0Name, gpu.displayName)}</strong>
                        </td>
                        <td>${location.city}, ${location.country}</td>
                        <td style="color: var(--accent-green); font-weight: 600;">$${gpu.price_per_hr.toFixed(2)}</td>
                        <td>${gpu.max_count}x</td>
                        <td>${resources.max_vcpus || '?'}</td>
                        <td>${resources.max_ram_gb || '?'} GB</td>
                        <td>${resources.max_storage_gb || '?'} GB</td>
                        <td class="feature-badges">
                            ${hasIp ? '<span class="feature-badge feature-ip">IP</span>' : ''}
                            ${hasPort ? '<span class="feature-badge feature-port">Port</span>' : ''}
                            ${hasStorage ? '<span class="feature-badge feature-storage">NAS</span>' : ''}
                            ${isMultiGpu ? '<span class="feature-badge feature-multi">Multi</span>' : ''}
                        </td>
                        <td>
                            ${(() => {
                                const key = location.id + '_' + gpu.v0Name;
                                const status = availabilityState[key];
                                if (status === true) return '<span style="color: var(--accent-green); font-weight: 600;">Yes</span>';
                                if (status === false) return '<span style="color: var(--accent-red); font-weight: 600;">No</span>';
                                return '<span style="color: var(--text-muted);">-</span>';
                            })()}
                        </td>
                        <td>
                            <button class="btn" style="padding: 0.35rem 0.5rem; font-size: 0.7rem;" onclick="copyLocationId('${location.id}')">📋</button>
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            document.getElementById('content').innerHTML = html;
        }

        // Initialize when DOM is ready
        function initApp() {
            document.getElementById('search').addEventListener('input', (e) => {
                searchQuery = e.target.value;
                renderData();
            });

            document.getElementById('sort').addEventListener('change', (e) => {
                currentSort = e.target.value;
                renderData();
            });

            document.getElementById('filters').addEventListener('click', (e) => {
                if (e.target.classList.contains('filter-btn')) {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    currentFilter = e.target.dataset.filter;
                    renderData();
                }
            });

            document.querySelector('.view-toggle').addEventListener('click', (e) => {
                if (e.target.classList.contains('view-btn')) {
                    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    currentView = e.target.dataset.view;
                    renderData();
                }
            });

            document.getElementById('auto-refresh').addEventListener('change', (e) => {
                if (e.target.checked) {
                    startAutoRefresh();
                } else {
                    stopAutoRefresh();
                }
            });

            // Cost calculator inputs - use arrow functions to ensure proper binding
            document.querySelectorAll('#cost-modal input, #cost-modal select').forEach(el => {
                el.addEventListener('input', () => calculateCost());
                el.addEventListener('change', () => calculateCost());
            });

            // Close modal on overlay click
            document.getElementById('cost-modal').addEventListener('click', (e) => {
                if (e.target.id === 'cost-modal') closeCostCalculator();
            });

            // Load availability cache first, then load GPU data
            loadAvailabilityCache().then(() => loadData());
        }

        // Run immediately if DOM already loaded, otherwise wait
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initApp);
        } else {
            initApp();
        }

        function startAutoRefresh() {
            let countdown = 30;
            document.getElementById('auto-refresh-indicator').style.display = 'block';

            autoRefreshInterval = setInterval(() => {
                countdown--;
                document.getElementById('countdown').textContent = countdown;
                if (countdown <= 0) {
                    loadData();
                    countdown = 30;
                }
            }, 1000);
        }

        function stopAutoRefresh() {
            clearInterval(autoRefreshInterval);
            document.getElementById('auto-refresh-indicator').style.display = 'none';
        }

        function copyLocationId(id) {
            navigator.clipboard.writeText(id);
            showToast('Location ID copied!');
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2000);
        }

        // Cost Calculator
        function updateCalcDropdown() {
            const select = document.getElementById('calc-gpu');
            select.innerHTML = '';

            const gpuMap = new Map();
            allData.forEach(loc => {
                loc.gpus.forEach(gpu => {
                    if (!gpuMap.has(gpu.v0Name)) {
                        gpuMap.set(gpu.v0Name, gpu);
                    }
                });
            });

            Array.from(gpuMap.entries()).sort((a, b) => a[1].price_per_hr - b[1].price_per_hr).forEach(([name, gpu]) => {
                select.innerHTML += `<option value="${name}" data-price="${gpu.price_per_hr}" data-vcpu-price="${gpu.pricing?.per_vcpu_hr || 0.003}" data-ram-price="${gpu.pricing?.per_gb_ram_hr || 0.002}" data-storage-price="${gpu.pricing?.per_gb_storage_hr || 0.00005}">${formatGpuName(name, gpu.displayName)} - $${gpu.price_per_hr.toFixed(2)}/hr</option>`;
            });
        }

        function openCostCalculator() {
            document.getElementById('cost-modal').classList.add('active');
            calculateCost();
        }

        let selectedLocationId = null;
        let selectedLocationName = '';

        function openCostCalculatorFor(gpuName, locationId) {
            document.getElementById('calc-gpu').value = gpuName;
            selectedLocationId = locationId;
            // Find location name
            const loc = allData.find(l => l.id === locationId);
            selectedLocationName = loc ? `${loc.city}, ${loc.country}` : locationId;
            // Update location display
            const locEl = document.getElementById('calc-location');
            if (locEl) locEl.innerHTML = `<option value="${locationId}">${selectedLocationName}</option>`;
            openCostCalculator();
        }

        function closeCostCalculator() {
            document.getElementById('cost-modal').classList.remove('active');
        }

        function calculateCost() {
            const select = document.getElementById('calc-gpu');
            const option = select.options[select.selectedIndex];
            if (!option) return;

            const gpuPrice = parseFloat(option.dataset.price) || 0;
            const vcpuPrice = parseFloat(option.dataset.vcpuPrice) || 0.003;
            const ramPrice = parseFloat(option.dataset.ramPrice) || 0.002;
            const storagePrice = parseFloat(option.dataset.storagePrice) || 0.00005;

            const gpuCount = parseInt(document.getElementById('calc-gpu-count').value) || 1;
            const vcpus = parseInt(document.getElementById('calc-vcpus').value) || 8;
            const ram = parseInt(document.getElementById('calc-ram').value) || 32;
            const storage = parseInt(document.getElementById('calc-storage').value) || 250;
            const hours = parseInt(document.getElementById('calc-hours').value) || 8;

            const gpuTotal = gpuPrice * gpuCount;
            const vcpuTotal = vcpuPrice * vcpus;
            const ramTotal = ramPrice * ram;
            const storageTotal = storagePrice * storage;
            const hourlyTotal = gpuTotal + vcpuTotal + ramTotal + storageTotal;
            const dailyTotal = hourlyTotal * hours;
            const monthlyTotal = dailyTotal * 30;

            document.getElementById('cost-result').innerHTML = `
                <div class="cost-total">$${hourlyTotal.toFixed(2)}/hr</div>
                <div class="cost-breakdown">
                    GPUs: $${gpuTotal.toFixed(2)} + vCPU: $${vcpuTotal.toFixed(3)} + RAM: $${ramTotal.toFixed(3)} + Storage: $${storageTotal.toFixed(4)}<br>
                    Daily (${hours}h): <strong>$${dailyTotal.toFixed(2)}</strong> • Monthly: <strong>$${monthlyTotal.toFixed(2)}</strong>
                </div>
            `;
        }

        // Update cost on input change
        document.querySelectorAll('#cost-modal input, #cost-modal select').forEach(el => {
            el.addEventListener('input', calculateCost);
            el.addEventListener('change', calculateCost);
        });

        function copyDeploymentJson() {
            const gpuName = document.getElementById('calc-gpu').value;
            const gpuCount = parseInt(document.getElementById('calc-gpu-count').value) || 1;
            const vcpus = parseInt(document.getElementById('calc-vcpus').value) || 8;
            const ram = parseInt(document.getElementById('calc-ram').value) || 32;
            const storage = parseInt(document.getElementById('calc-storage').value) || 250;

            const json = {
                "data": {
                    "type": "virtualmachine",
                    "attributes": {
                        "name": "my-instance",
                        "image": "windows10",
                        "location_id": "<PASTE_LOCATION_ID>",
                        "useDedicatedIp": true,
                        "resources": {
                            "vcpu_count": vcpus,
                            "ram_gb": ram,
                            "storage_gb": storage,
                            "gpus": {
                                [gpuName]: { "count": gpuCount }
                            }
                        },
                        "password": "YourSecurePass123!@"
                    }
                }
            };

            navigator.clipboard.writeText(JSON.stringify(json, null, 2));
            showToast('Deployment JSON copied!');
        }

        // Tab switching
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const tabName = tab.dataset.tab;
                document.getElementById('gpus-tab').style.display = tabName === 'gpus' ? 'block' : 'none';
                document.getElementById('instances-tab').style.display = tabName === 'instances' ? 'block' : 'none';
                if (tabName === 'instances') loadInstances();
            });
        });

        // Update location dropdown
        function updateLocationDropdown() {
            const select = document.getElementById('calc-location');
            if (!select) return;
            select.innerHTML = '';
            allData.forEach(loc => {
                select.innerHTML += `<option value="${loc.id}">${loc.city}, ${loc.country}</option>`;
            });
        }

        // Password validation
        function validatePassword(pw) {
            return pw && pw.length >= 10 && /[A-Z]/.test(pw) && /[0-9]/.test(pw) && /[!@#$%^&*]/.test(pw);
        }

        // Update password hint on input
        document.getElementById('calc-password')?.addEventListener('input', (e) => {
            const hint = document.getElementById('password-hint');
            if (e.target.value.length > 0) {
                hint.className = validatePassword(e.target.value) ? 'password-hint password-valid' : 'password-hint password-invalid';
                hint.textContent = validatePassword(e.target.value) ? '✓ Password valid' : '✗ Min 10 chars, 1 uppercase, 1 number, 1 symbol';
            }
        });

        // Deploy VM
        async function deployVM() {
            const gpuName = document.getElementById('calc-gpu').value;
            const gpuCount = parseInt(document.getElementById('calc-gpu-count').value) || 1;
            const vcpus = parseInt(document.getElementById('calc-vcpus').value) || 8;
            const ram = parseInt(document.getElementById('calc-ram').value) || 32;
            const storage = parseInt(document.getElementById('calc-storage').value) || 250;
            const locationId = selectedLocationId || document.getElementById('calc-location')?.value;
            const password = document.getElementById('calc-password').value;

            if (!locationId) {
                showToast('No location selected! Click Deploy on a GPU card.', true);
                return;
            }

            if (!validatePassword(password)) {
                showToast('Invalid password! Need 10+ chars, uppercase, number, symbol', true);
                return;
            }

            const btn = document.getElementById('deploy-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Deploying...';

            try {
                const resp = await fetch('/api/deploy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: 'my-windows-vm',
                        gpu: gpuName,
                        gpu_count: gpuCount,
                        vcpus, ram, storage,
                        location_id: locationId,
                        password
                    })
                });
                const data = await resp.json();

                // Check for success - API may return 200 with error in body
                if (data.success && !data.error && data.data?.status !== 400) {
                    showToast('🎉 VM deployed successfully!');
                    closeCostCalculator();
                    document.querySelector('[data-tab="instances"]').click();
                } else {
                    const errorMsg = data.error || data.data?.error || 'Unknown error';
                    showToast('Deploy failed: ' + errorMsg, true);
                }
            } catch (e) {
                showToast('Error: ' + e.message, true);
            } finally {
                btn.disabled = false;
                btn.textContent = '🚀 Deploy Now';
            }
        }

        // Show toast with error support
        function showToast(msg, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = isError ? 'toast error show' : 'toast show';
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        // Load instances
        async function loadInstances() {
            document.getElementById('instances-content').innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading...</div>';
            try {
                const resp = await fetch('/api/instances');
                const data = await resp.json();
                renderInstances(data.instances || []);
            } catch (e) {
                document.getElementById('instances-content').innerHTML = '<div class="loading" style="color:var(--accent-red);">Error loading instances</div>';
            }
        }

        function renderInstances(instances) {
            if (instances.length === 0) {
                document.getElementById('instances-content').innerHTML = '<div class="empty-state"><h3>No instances yet</h3><p>Deploy a VM from the Available GPUs tab</p></div>';
                return;
            }

            let html = '';
            instances.forEach(inst => {
                const status = inst.status || 'unknown';
                const statusClass = status.toLowerCase().includes('running') ? 'running' : status.toLowerCase().includes('stop') ? 'stopped' : 'starting';
                const ip = inst.ipAddress || 'N/A';
                const ports = inst.portForwards || [];
                const rdpPort = ports.find(p => p.internal_port === 3389)?.external_port || '3389';
                const resources = inst.resources || {};
                const gpuInfo = Object.entries(resources.gpus || {}).map(([k,v]) => `${v.count}x ${formatGpuName(k, '')}`).join(', ') || 'N/A';

                html += `
                    <div class="instance-card">
                        <div class="instance-header">
                            <div class="instance-name">${inst.name || inst.id}</div>
                            <span class="status-badge status-${statusClass}">${status}</span>
                        </div>
                        <div class="instance-details">
                            <div class="detail-group"><div class="detail-label">Connection (RDP)</div><div class="detail-value">${ip}:${rdpPort}</div></div>
                            <div class="detail-group"><div class="detail-label">GPU</div><div class="detail-value">${gpuInfo}</div></div>
                            <div class="detail-group"><div class="detail-label">Resources</div><div class="detail-value">${resources.vcpu_count || '?'} vCPUs, ${resources.ram_gb || '?'} GB RAM</div></div>
                            <div class="detail-group"><div class="detail-label">Hourly Rate</div><div class="detail-value" style="color:var(--accent-green);">$${(inst.rateHourly || 0).toFixed(2)}/hr</div></div>
                        </div>
                        <div class="instance-actions">
                            <button class="btn" onclick="navigator.clipboard.writeText('mstsc /v:${ip}:${rdpPort}'); showToast('RDP command copied!');">📋 Copy RDP</button>
                            ${statusClass === 'stopped' ? `<button class="btn btn-success" onclick="startInstance('${inst.id}')">▶️ Start</button>` : ''}
                            ${statusClass === 'running' ? `<button class="btn btn-primary" onclick="stopInstance('${inst.id}')">⏹️ Stop</button>` : ''}
                            <button class="btn btn-danger" onclick="deleteInstance('${inst.id}')">🗑️ Delete</button>
                        </div>
                    </div>
                `;
            });
            document.getElementById('instances-content').innerHTML = html;
        }

        async function startInstance(id) {
            if (!confirm('Start this instance?')) return;
            showToast('Starting instance...');
            try {
                const resp = await fetch(`/api/instances/${id}/start`, { method: 'POST' });
                if (resp.ok) { showToast('Instance starting!'); loadInstances(); }
                else showToast('Failed to start', true);
            } catch (e) { showToast('Error: ' + e.message, true); }
        }

        async function stopInstance(id) {
            if (!confirm('Stop this instance?')) return;
            showToast('Stopping instance...');
            try {
                const resp = await fetch(`/api/instances/${id}/stop`, { method: 'POST' });
                if (resp.ok) { showToast('Instance stopping!'); loadInstances(); }
                else showToast('Failed to stop', true);
            } catch (e) { showToast('Error: ' + e.message, true); }
        }

        async function deleteInstance(id) {
            if (!confirm('DELETE this instance? This cannot be undone!')) return;
            showToast('Deleting instance...');
            try {
                const resp = await fetch(`/api/instances/${id}`, { method: 'DELETE' });
                if (resp.ok) { showToast('Instance deleted!'); loadInstances(); }
                else showToast('Failed to delete', true);
            } catch (e) { showToast('Error: ' + e.message, true); }
        }

        // Test availability of all visible GPU cards
        async function testAllAvailability() {
            const btn = document.getElementById('test-availability-btn');
            btn.disabled = true;
            btn.textContent = '🔄 Testing...';

            // Reset availability state for a fresh test
            availabilityState = {};

            // Get all unique GPU/location combos from data (not just visible cards)
            const toTest = [];
            allData.forEach(loc => {
                (loc.gpus || []).forEach(gpu => {
                    toTest.push({ locationId: loc.id, v0Name: gpu.v0Name, location: loc, gpu });
                });
            });

            let tested = 0;
            let available = 0;
            let unavailable = 0;

            showToast(`Testing ${toTest.length} GPUs... This may take a moment.`);

            for (const { locationId, v0Name } of toTest) {
                const key = locationId + '_' + v0Name;

                try {
                    const resp = await fetch('/api/test-deploy', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            gpu: v0Name,
                            location_id: locationId,
                            vcpus: 4,
                            ram: 8,
                            storage: 100,
                            gpu_count: 1
                        })
                    });
                    const data = await resp.json();

                    if (data.available) {
                        availabilityState[key] = true;
                        available++;
                    } else {
                        availabilityState[key] = false;
                        unavailable++;
                    }
                } catch (e) {
                    availabilityState[key] = false;
                    unavailable++;
                }
                tested++;
                btn.textContent = `🔄 Testing ${tested}/${toTest.length}...`;

                // Update card classes if in card view
                const card = document.querySelector(`.gpu-card[data-location-id="${locationId}"][data-gpu-name="${v0Name}"]`);
                if (card) {
                    card.classList.remove('testing', 'unavailable', 'available');
                    card.classList.add(availabilityState[key] ? 'available' : 'unavailable');
                }
            }

            btn.disabled = false;
            btn.textContent = '🧪 Test All Availability';
            showToast(`Done! ✅ ${available} available, ❌ ${unavailable} unavailable`);

            // Re-render to update table view with availability status
            renderData();
        }

        // Helper to find v0Name for a card's location
        function findV0Name(locationId, card) {
            const location = allData.find(l => l.id === locationId);
            if (!location) return null;
            // Get the first GPU from this location (since card represents one GPU at one location)
            const cardTitle = card.querySelector('h3')?.textContent || '';
            for (const gpu of location.gpus || []) {
                const formatted = formatGpuName(gpu.v0Name);
                if (cardTitle.includes(formatted.split(' ').slice(-1)[0])) {
                    return gpu.v0Name;
                }
            }
            return location.gpus?.[0]?.v0Name;
        }
    </script>
</body>
</html>
"""


class GPUDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())

        elif parsed.path == "/api/data":
            self._send_json(self._get_cached_locations())

        elif parsed.path == "/api/instances":
            self._send_json(self._get_instances())

        elif parsed.path.startswith("/api/instances/") and not parsed.path.endswith("/start") and not parsed.path.endswith("/stop"):
            instance_id = parsed.path.split("/")[-1]
            self._send_json(self._get_instance_details(instance_id))

        elif parsed.path == "/api/availability":
            self._send_json(_availability_cache)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        if parsed.path == "/api/deploy":
            data = json.loads(body)
            result = self._deploy_vm(data)
            self._send_json(result)

        elif "/start" in parsed.path:
            instance_id = parsed.path.split("/")[-2]
            result = self._start_instance(instance_id)
            self._send_json(result)

        elif "/stop" in parsed.path:
            instance_id = parsed.path.split("/")[-2]
            result = self._stop_instance(instance_id)
            self._send_json(result)

        elif parsed.path == "/api/test-deploy":
            data = json.loads(body)
            result = self._test_availability(data)
            self._send_json(result)
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/instances/"):
            instance_id = parsed.path.split("/")[-1]
            result = self._delete_instance(instance_id)
            self._send_json(result)
        else:
            self.send_error(404)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _headers(self):
        return {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json", "Content-Type": "application/json"}

    def _get_cached_locations(self):
        global _cache
        now = time.time()

        if _cache["data"] is not None:
            response_data = _cache["data"].copy()
            response_data["_cached"] = True
            response_data["_cache_age"] = int(now - _cache["timestamp"])

            if now - _cache["timestamp"] > CACHE_TTL and not _cache["fetching"]:
                threading.Thread(target=self._refresh_cache, daemon=True).start()
            return response_data

        self._fetch_and_cache()
        return _cache["data"] if _cache["data"] else {"error": "Failed to fetch data"}

    def _get_instances(self):
        try:
            resp = requests.get(f"{BASE_URL}/instances", headers=self._headers(), timeout=10)
            resp.raise_for_status()
            instances_list = resp.json().get("data", {}).get("instances", [])
            detailed = []
            for inst in instances_list:
                inst_id = inst.get("id")
                if inst_id:
                    detail = self._get_instance_details(inst_id)
                    if detail and not detail.get("error"):
                        detailed.append(detail)
                    else:
                        detailed.append(inst)
            return {"instances": detailed}
        except Exception as e:
            return {"error": str(e), "instances": []}

    def _get_instance_details(self, instance_id):
        try:
            resp = requests.get(f"{BASE_URL}/instances/{instance_id}", headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _deploy_vm(self, data):
        # Auto-encode my_setup.bat to base64 at deploy time
        import base64

        setup_script_b64 = ""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            bat_path = os.path.join(script_dir, "my_setup.bat")
            with open(bat_path, "rb") as f:
                setup_script_b64 = base64.b64encode(f.read()).decode("utf-8")
            print(f"[Deploy] Encoded my_setup.bat ({len(setup_script_b64)} chars)")
        except Exception as e:
            print(f"[Deploy] Warning: Could not encode setup script: {e}")

        payload = {
            "data": {
                "type": "virtualmachine",
                "attributes": {
                    "name": data.get("name", "my-instance"),
                    "type": "virtualmachine",
                    "image": "windows10",
                    "location_id": data.get("location_id"),
                    "useDedicatedIp": False,
                    "resources": {
                        "vcpu_count": data.get("vcpus", 8),
                        "ram_gb": data.get("ram", 32),
                        "storage_gb": data.get("storage", 250),
                        "gpus": {data.get("gpu"): {"count": data.get("gpu_count", 1)}},
                    },
                    "port_forwards": [{"internal_port": 3389, "external_port": 33389, "protocol": "tcp"}],
                    "password": data.get("password"),
                    "cloud_init": {
                        "write_files": [
                            {"path": "C:\\Users\\user\\Desktop\\my_setup.bat", "content": setup_script_b64, "encoding": "base64"}
                        ],
                        "runcmd": [
                            "echo VM deployed from TensorDock Dashboard > C:\\deploy_info.txt",
                            "echo Executing setup script... >> C:\\deploy_info.txt",
                            "C:\\Users\\user\\Desktop\\my_setup.bat > C:\\setup_log.txt 2>&1",
                        ],
                    },
                },
            }
        }
        try:
            print(f"[Deploy] Sending request: {json.dumps(payload, indent=2)}")
            resp = requests.post(f"{BASE_URL}/instances", headers=self._headers(), json=payload, timeout=30)
            print(f"[Deploy] Response {resp.status_code}: {resp.text}")
            result = resp.json()
            # Check for error in response body (API returns 200 with error inside)
            if result.get("status") == 400 or result.get("error"):
                return {"success": False, "error": result.get("error", "API error")}
            if resp.status_code in [200, 201]:
                return {"success": True, "data": result}
            else:
                return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _start_instance(self, instance_id):
        try:
            resp = requests.post(f"{BASE_URL}/instances/{instance_id}/start", headers=self._headers(), timeout=10)
            return {"success": resp.status_code in [200, 201, 204]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _stop_instance(self, instance_id):
        try:
            resp = requests.post(f"{BASE_URL}/instances/{instance_id}/stop", headers=self._headers(), timeout=10)
            return {"success": resp.status_code in [200, 201, 204]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _delete_instance(self, instance_id):
        try:
            resp = requests.delete(f"{BASE_URL}/instances/{instance_id}", headers=self._headers(), timeout=10)
            return {"success": resp.status_code in [200, 201, 204]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _test_availability(self, data):
        """Test if a GPU is available by attempting to deploy (with a fake password that will fail validation but after resource check)."""
        global _availability_cache

        location_id = data.get("location_id")
        gpu_name = data.get("gpu")
        cache_key = f"{location_id}_{gpu_name}"

        payload = {
            "data": {
                "type": "virtualmachine",
                "attributes": {
                    "name": "availability-test",
                    "type": "virtualmachine",
                    "image": "windows10",
                    "location_id": location_id,
                    "useDedicatedIp": False,
                    "resources": {
                        "vcpu_count": data.get("vcpus", 4),
                        "ram_gb": data.get("ram", 8),
                        "storage_gb": data.get("storage", 100),
                        "gpus": {gpu_name: {"count": data.get("gpu_count", 1)}},
                    },
                    "port_forwards": [{"internal_port": 3389, "external_port": 33389, "protocol": "tcp"}],
                    "password": "TestPass123!@#",  # Valid password format for test
                },
            }
        }
        try:
            resp = requests.post(f"{BASE_URL}/instances", headers=self._headers(), json=payload, timeout=15)
            result = resp.json()

            # If we get "No available nodes" error, it's unavailable
            if result.get("status") == 400 and "No available nodes" in result.get("error", ""):
                cache_result = {"available": False, "reason": result.get("error"), "timestamp": time.time()}
                _availability_cache[cache_key] = cache_result
                _save_availability_cache()
                return {"available": False, "reason": result.get("error")}

            # If deploy started successfully, delete it immediately and mark as available
            if resp.status_code in [200, 201] and result.get("data", {}).get("id"):
                instance_id = result.get("data", {}).get("id")
                # Delete the test instance immediately
                requests.delete(f"{BASE_URL}/instances/{instance_id}", headers=self._headers(), timeout=10)
                cache_result = {"available": True, "reason": None, "timestamp": time.time()}
                _availability_cache[cache_key] = cache_result
                _save_availability_cache()
                return {"available": True}

            # Any other error means unavailable
            cache_result = {"available": False, "reason": result.get("error", "Unknown"), "timestamp": time.time()}
            _availability_cache[cache_key] = cache_result
            _save_availability_cache()
            return {"available": False, "reason": result.get("error", "Unknown")}
        except Exception as e:
            cache_result = {"available": False, "reason": str(e), "timestamp": time.time()}
            _availability_cache[cache_key] = cache_result
            _save_availability_cache()
            return {"available": False, "reason": str(e)}

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def _fetch_and_cache(self):
        """Fetch data from TensorDock API and update cache."""
        global _cache
        _cache["fetching"] = True

        headers = {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json"}
        try:
            response = requests.get(f"{BASE_URL}/locations", headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json().get("data", {})
            _cache["data"] = data
            _cache["timestamp"] = time.time()
            print(f"[Cache] Updated with {len(data.get('locations', []))} locations")
        except Exception as e:
            print(f"[Cache] Fetch error: {e}")
        finally:
            _cache["fetching"] = False

    def _refresh_cache(self):
        """Background refresh of cache."""
        print("[Cache] Starting background refresh...")
        self._fetch_and_cache()


def main():
    port = 8080

    # Pre-warm cache before starting server
    print("⏳ Pre-warming cache (fetching GPU data from TensorDock API)...")
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json"}
    try:
        response = requests.get(f"{BASE_URL}/locations", headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json().get("data", {})
        _cache["data"] = data
        _cache["timestamp"] = time.time()
        print(f"✅ Cache ready with {len(data.get('locations', []))} locations")
    except Exception as e:
        print(f"⚠️ Cache pre-warm failed: {e} (will fetch on first request)")

    # Load availability cache from file
    _load_availability_cache()

    server = http.server.HTTPServer(("localhost", port), GPUDashboardHandler)
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║         🚀 TensorDock GPU Dashboard v3                            ║
╠═══════════════════════════════════════════════════════════════════╣
║  Features:                                                        ║
║    • 🔍 Search by GPU name or location                            ║
║    • 📊 Sort by price, vCPUs, RAM, or tier                        ║
║    • 💰 Cost calculator with deployment                           ║
║    • 🚀 Deploy VMs directly from dashboard                        ║
║    • 📋 My Instances - manage running VMs                         ║
║    • ▶️ Start / ⏹️ Stop / 🗑️ Delete instances                      ║
║    • 🧪 Test All Availability - verify real GPU access            ║
╠═══════════════════════════════════════════════════════════════════╣
║  Open your browser to: http://localhost:{port}                      ║
║  Press Ctrl+C to stop                                             ║
╚═══════════════════════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
