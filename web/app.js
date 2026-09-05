/* ============================================================
   app.js — Quantum VRP Interactive Platform Frontend Logic
   Comprehensive Route Optimization & Comparative Benchmarking
   ============================================================ */

// ---- Global State ----
let map = null;
let depotMarker = null;
let customerMarkers = [];
let routeLayers = {};
let selectedCity = 'delhi';
let convergenceChart = null;
let bigConvergenceChart = null;
let latestSimulationData = null;
let activeManifestAlgo = 'exact';

const ALGO_COLORS = {
    qpso:  '#10b981', // Emerald
    ga:    '#ef4444', // Crimson
    exact: '#f59e0b'  // Amber
};

const ALGO_NAMES = {
    qpso:  'Delta-Well QPSO',
    ga:    'Classical Heuristic GA',
    exact: 'Exact Solver (OR-Tools)'
};

// Safe DOM text setter helper
function setElText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function setElHtml(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

function selectAllAlgos() {
    const q = document.getElementById('algoQPSO');
    const g = document.getElementById('algoGA');
    const e = document.getElementById('algoExact');
    if (q) q.checked = true;
    if (g) g.checked = true;
    if (e) e.checked = true;
}

// ---- View Mode Switching ----
function switchView(viewName) {
    const tabMap = document.getElementById('tabMap');
    const tabComp = document.getElementById('tabComparison');
    const viewMap = document.getElementById('viewMap');
    const viewComp = document.getElementById('viewComparison');

    if (viewName === 'map') {
        if (tabMap) tabMap.classList.add('active');
        if (tabComp) tabComp.classList.remove('active');
        if (viewMap) viewMap.classList.add('active');
        if (viewComp) viewComp.classList.remove('active');

        setTimeout(() => {
            if (map) map.invalidateSize();
        }, 150);
    } else {
        if (tabComp) tabComp.classList.add('active');
        if (tabMap) tabMap.classList.remove('active');
        if (viewComp) viewComp.classList.add('active');
        if (viewMap) viewMap.classList.remove('active');

        // Always refresh comparison matrix and charts when switching to comparison tab
        if (latestSimulationData) {
            renderComparisonMatrix(latestSimulationData);
        }
    }
}

// ---- Initialize Map ----
function initMap() {
    map = L.map('map', {
        zoomControl: true,
        attributionControl: true
    }).setView([28.6139, 77.2090], 11); // Delhi default

    // Clean Fastly CDN dark tiles without watermark
    L.tileLayer('https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a> | &copy; OpenStreetMap contributors',
        maxZoom: 18,
        subdomains: 'abcd'
    }).addTo(map);

    // Place default depot at Delhi
    placeDepot(28.6139, 77.2090);

    // Click map to reposition depot
    map.on('click', function(e) {
        placeDepot(e.latlng.lat, e.latlng.lng);
        selectedCity = null;
        const sel = document.getElementById('citySelect');
        if (sel) sel.value = '';
    });
}

// ---- Load Cities Dropdown ----
async function loadCities() {
    try {
        const resp = await fetch('/api/cities');
        const cities = await resp.json();
        const sel = document.getElementById('citySelect');
        if (!sel) return;

        sel.innerHTML = '<option value="">— Select City or Click Map —</option>';
        cities.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.key;
            opt.textContent = `${c.name} (${c.state})${c.available ? '' : ' [Download]'}`;
            opt.dataset.lat = c.lat;
            opt.dataset.lon = c.lon;
            if (c.key === 'delhi') opt.selected = true;
            sel.appendChild(opt);
        });

        sel.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            if (opt && opt.value) {
                selectedCity = opt.value;
                const lat = parseFloat(opt.dataset.lat);
                const lon = parseFloat(opt.dataset.lon);
                map.flyTo([lat, lon], 12, { duration: 1.2 });
                placeDepot(lat, lon);
            } else {
                selectedCity = null;
            }
        });

        selectedCity = 'delhi';
    } catch (e) {
        console.error('Failed to load cities:', e);
    }
}

// ---- Depot Placement ----
function placeDepot(lat, lon) {
    const latEl = document.getElementById('depotLat');
    const lonEl = document.getElementById('depotLon');
    if (latEl) latEl.value = lat.toFixed(4);
    if (lonEl) lonEl.value = lon.toFixed(4);

    if (depotMarker && map) map.removeLayer(depotMarker);

    const icon = L.divIcon({
        html: `<div style="
            width:30px; height:30px; border-radius:50%;
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            border: 3px solid white;
            box-shadow: 0 0 20px rgba(245,158,11,0.8);
            display:flex; align-items:center; justify-content:center;
            font-size:16px;
        ">⭐</div>`,
        className: '',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });

    if (map) {
        depotMarker = L.marker([lat, lon], { icon, draggable: true })
            .addTo(map)
            .bindPopup('<b>Depot (Distribution Hub)</b><br>Drag marker or click anywhere to reposition');

        depotMarker.on('dragend', function(e) {
            const pos = e.target.getLatLng();
            if (latEl) latEl.value = pos.lat.toFixed(4);
            if (lonEl) lonEl.value = pos.lng.toFixed(4);
            selectedCity = null;
            const sel = document.getElementById('citySelect');
            if (sel) sel.value = '';
        });
    }
}

// ---- Slider Setup ----
function initSliders() {
    const sliders = [
        { id: 'numVehicles', display: 'vehVal' },
        { id: 'numCustomers', display: 'custVal' },
        { id: 'capacity', display: 'capVal' },
    ];
    sliders.forEach(s => {
        const el = document.getElementById(s.id);
        const disp = document.getElementById(s.display);
        if (el && disp) {
            el.addEventListener('input', () => {
                disp.textContent = el.value;
            });
        }
    });
}

// ---- Run Simulation ----
async function runSimulation() {
    const btn = document.getElementById('btnRun');
    const progress = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const statusText = document.getElementById('systemStatus');
    const statusDot = document.querySelector('.status-indicator');

    const depotLat = parseFloat(document.getElementById('depotLat').value);
    const depotLon = parseFloat(document.getElementById('depotLon').value);

    if (isNaN(depotLat) || isNaN(depotLon)) {
        alert('Please select a city or click on the map to place a depot first.');
        return;
    }

    const algorithms = [];
    const qCheck = document.getElementById('algoQPSO');
    const gCheck = document.getElementById('algoGA');
    const eCheck = document.getElementById('algoExact');

    if (qCheck && qCheck.checked) algorithms.push('qpso');
    if (gCheck && gCheck.checked) algorithms.push('ga');
    if (eCheck && eCheck.checked) algorithms.push('exact');

    if (algorithms.length === 0) {
        alert('Please select at least one algorithm to run simulation.');
        return;
    }

    const payload = {
        city_key: selectedCity || null,
        depot_lat: depotLat,
        depot_lon: depotLon,
        num_vehicles: parseInt(document.getElementById('numVehicles').value),
        num_customers: parseInt(document.getElementById('numCustomers').value),
        capacity: parseInt(document.getElementById('capacity').value),
        algorithms: algorithms
    };

    // UI Loading State
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Optimizing Routes...';
        btn.classList.add('running');
    }
    if (progress) progress.classList.add('active');
    if (progressText) progressText.textContent = 'Submitting job to solver engine...';
    if (statusText) statusText.textContent = 'Optimization in Progress...';
    if (statusDot) statusDot.classList.add('running');

    const overlay = document.getElementById('resultsOverlay');
    if (overlay) overlay.classList.remove('active');
    clearMap();

    try {
        const resp = await fetch('/api/solve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const { job_id } = await resp.json();

        // Poll for completion
        let result = null;
        while (!result) {
            await sleep(700);
            const statusResp = await fetch(`/api/status/${job_id}`);
            const status = await statusResp.json();
            if (progressText) progressText.textContent = status.progress || 'Optimizing...';

            if (status.status === 'done') {
                result = status.results;
            } else if (status.status === 'error') {
                throw new Error(status.progress);
            }
        }

        // Render full suite (map + comparison)
        renderResults(result);

        if (statusText) statusText.textContent = 'Simulation Complete & Benchmarked';
        if (statusDot) statusDot.classList.remove('running');

    } catch (e) {
        alert('Simulation failed: ' + e.message);
        console.error('Simulation error:', e);
        if (statusText) statusText.textContent = 'Simulation Error';
        if (statusDot) statusDot.classList.remove('running');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '▶ Run Simulation';
            btn.classList.remove('running');
        }
        if (progress) progress.classList.remove('active');
    }
}

// ---- Render Results (Map + Trigger Comparison Matrix) ----
function renderResults(data) {
    if (!data) return;
    latestSimulationData = data;

    try {
        // 1. Plot customers on map
        if (data.customers && map) {
            data.customers.forEach((c, i) => {
                const icon = L.divIcon({
                    html: `<div style="
                        width:11px; height:11px; border-radius:50%;
                        background:#38bdf8; border:2px solid #0f172a;
                        box-shadow: 0 0 6px rgba(56,189,248,0.7);
                    "></div>`,
                    className: '',
                    iconSize: [11, 11],
                    iconAnchor: [5.5, 5.5]
                });
                const m = L.marker([c.lat, c.lon], { icon })
                    .addTo(map)
                    .bindPopup(`<b>Customer Node #${i+1}</b><br>Package Demand: <b>${c.demand} units</b>`);
                customerMarkers.push(m);
            });

            // Fit map bounds
            if (data.depot) {
                const allPts = [[data.depot.lat, data.depot.lon], ...data.customers.map(c => [c.lat, c.lon])];
                map.fitBounds(allPts, { padding: [50, 50] });
            }
        }

        // 2. Draw routes for each algorithm
        const algos = data.algorithms || {};
        const algoKeys = Object.keys(algos);
        const togglesEl = document.getElementById('routeToggles');
        if (togglesEl) togglesEl.innerHTML = '';

        algoKeys.forEach(key => {
            const algo = algos[key];
            if (!algo || !algo.route_coords || algo.route_coords.length === 0) return;

            const color = ALGO_COLORS[key] || '#888';
            const layers = [];

            algo.route_coords.forEach((routeCoords) => {
                const latlngs = routeCoords.map(p => [p.lat, p.lon]);
                const polyline = L.polyline(latlngs, {
                    color: color,
                    weight: key === 'qpso' ? 3.5 : 2.5,
                    opacity: 0.85,
                    dashArray: key === 'ga' ? '8 6' : (key === 'exact' ? '4 4' : null)
                }).addTo(map);
                layers.push(polyline);
            });

            routeLayers[key] = layers;

            // Toggle button on Map Overlay
            if (togglesEl) {
                const btn = document.createElement('button');
                btn.className = 'route-toggle active';
                btn.innerHTML = `<span style="color:${color}; font-size:14px;">●</span> ${ALGO_NAMES[key] || key}`;
                btn.dataset.algo = key;
                btn.onclick = function() {
                    this.classList.toggle('active');
                    const visible = this.classList.contains('active');
                    routeLayers[key].forEach(l => {
                        if (visible) l.addTo(map);
                        else map.removeLayer(l);
                    });
                };
                togglesEl.appendChild(btn);
            }
        });

        // 3. Find Best Distance
        let bestDist = Infinity, bestKey = '';
        algoKeys.forEach(key => {
            const d = algos[key].distance_km;
            if (d > 0 && d < bestDist) { bestDist = d; bestKey = key; }
        });

        const winnerBadgeEl = document.getElementById('winnerBadge');
        if (winnerBadgeEl) {
            winnerBadgeEl.textContent = bestKey ? `WINNER: ${bestKey.toUpperCase()}` : '—';
        }

        // 4. Build HUD Overlay Algorithm Cards
        const cardsEl = document.getElementById('algoCards');
        if (cardsEl) {
            cardsEl.innerHTML = '';
            algoKeys.forEach(key => {
                const algo = algos[key];
                if (!algo || (algo.distance_km <= 0 && !algo.error)) return;

                const color = ALGO_COLORS[key] || '#888';
                const isWinner = (key === bestKey);
                const card = document.createElement('div');
                card.className = 'results-card';

                if (algo.error) {
                    card.innerHTML = `
                        <h3>
                            <span class="dot" style="background:${color}"></span>
                            ${algo.algorithm || ALGO_NAMES[key]}
                        </h3>
                        <div style="font-size:12px; color:#f87171; padding:8px 0;">
                            ⚠️ ${algo.error}
                        </div>
                    `;
                } else {
                    card.innerHTML = `
                        <h3>
                            <span class="dot" style="background:${color}"></span>
                            ${algo.algorithm || ALGO_NAMES[key]}
                            ${isWinner ? '<span class="winner-badge">★ CHAMPION</span>' : ''}
                        </h3>
                        <div class="metric-grid">
                            <div class="metric-item">
                                <div class="metric-value" style="color:${color}">${algo.distance_km}</div>
                                <div class="metric-label">Distance (km)</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-value" style="color:${color}">${(algo.time_sec / 3600).toFixed(2)}h</div>
                                <div class="metric-label">Travel Time</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-value" style="color:${color}">${algo.runtime_sec.toFixed(2)}s</div>
                                <div class="metric-label">Runtime</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-value" style="color:${algo.violations > 0 ? '#ef4444' : color}">${algo.violations}</div>
                                <div class="metric-label">Violations</div>
                            </div>
                        </div>
                    `;
                }
                cardsEl.appendChild(card);
            });
        }

        // 5. Comparison Bars in Map Overlay
        const barsEl = document.getElementById('comparisonBars');
        if (barsEl) {
            barsEl.innerHTML = '';
            const validDists = algoKeys.map(k => algos[k].distance_km).filter(d => d > 0);
            const maxDist = validDists.length > 0 ? Math.max(...validDists) : 1;

            algoKeys.forEach(key => {
                const algo = algos[key];
                if (!algo || algo.distance_km <= 0) return;
                const pct = Math.max(12, (algo.distance_km / maxDist) * 100);
                const color = ALGO_COLORS[key];
                const row = document.createElement('div');
                row.className = 'comparison-bar';
                row.innerHTML = `
                    <div style="width:105px; font-size:11px; font-weight:700; color:${color}">
                        ${key.toUpperCase()}
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill ${key}" style="width:${pct}%; background:${color};"></div>
                    </div>
                    <div class="bar-label">${algo.distance_km} km</div>
                `;
                barsEl.appendChild(row);
            });
        }

        // 6. Quick Convergence Chart in Overlay
        renderConvergenceChart(algos);

        // Show Map HUD overlay
        const overlay = document.getElementById('resultsOverlay');
        if (overlay) overlay.classList.add('active');

    } catch (err) {
        console.error('Error in map renderResults:', err);
    }

    // 7. Render Comprehensive Comparison Matrix View
    try {
        renderComparisonMatrix(data);
    } catch (err) {
        console.error('Error in renderComparisonMatrix:', err);
    }
}

// ---- Render Dedicated Comparison Matrix View ----
function renderComparisonMatrix(data) {
    if (!data) return;
    const algos = data.algorithms || {};
    const config = data.config || {};

    // 1. Update Meta Tags
    setElText('metaTagCity', config.city_key ? config.city_key.toUpperCase() : 'Custom Location');
    setElText('metaTagCust', config.num_customers || (data.customers ? data.customers.length : '—'));
    setElText('metaTagVeh', config.num_vehicles || '—');
    setElText('metaTagCap', `${config.capacity || '—'} units`);
    setElText('metaTagTime', config.timestamp || new Date().toLocaleTimeString());

    setElText('compSubheading',
        `Benchmarking ${Object.keys(algos).length} algorithms on ${config.num_customers || (data.customers ? data.customers.length : '')} customer nodes with ${config.num_vehicles || ''} vehicles.`
    );

    // 2. Identify Winners & KPIs
    let bestDist = Infinity, bestDistAlgo = null;
    let fastestTime = Infinity, fastestAlgo = null;
    let gaDist = (algos.ga && algos.ga.distance_km > 0) ? algos.ga.distance_km : null;
    let totalViolations = 0;

    ['qpso', 'ga', 'exact'].forEach(k => {
        const a = algos[k];
        if (a && a.distance_km > 0) {
            if (a.distance_km < bestDist) {
                bestDist = a.distance_km;
                bestDistAlgo = k;
            }
            if (a.runtime_sec !== undefined && a.runtime_sec < fastestTime) {
                fastestTime = a.runtime_sec;
                fastestAlgo = k;
            }
            totalViolations += (a.violations || 0);
        }
    });

    // Hero KPI: Best Distance
    if (bestDistAlgo) {
        setElText('kpiBestAlgo', ALGO_NAMES[bestDistAlgo] || bestDistAlgo);
        setElText('kpiBestDist', `${bestDist.toFixed(2)} km`);
        if (gaDist && bestDistAlgo !== 'ga') {
            const saving = ((gaDist - bestDist) / gaDist * 100).toFixed(1);
            setElText('kpiDistMargin', `${saving}% shorter than GA`);
        } else {
            setElText('kpiDistMargin', 'Shortest fleet distance');
        }
    } else {
        setElText('kpiBestAlgo', '—');
        setElText('kpiBestDist', '— km');
        setElText('kpiDistMargin', '—');
    }

    // Hero KPI: Fastest
    if (fastestAlgo && fastestTime < Infinity) {
        setElText('kpiFastAlgo', ALGO_NAMES[fastestAlgo] || fastestAlgo);
        setElText('kpiFastTime', `${fastestTime.toFixed(2)} s`);
        if (algos.exact && algos.exact.runtime_sec > 0 && fastestAlgo !== 'exact') {
            const speedup = (algos.exact.runtime_sec / Math.max(0.001, fastestTime)).toFixed(1);
            setElText('kpiSpeedup', `${speedup}x faster than Exact`);
        } else {
            setElText('kpiSpeedup', 'Lowest optimization runtime');
        }
    } else {
        setElText('kpiFastAlgo', '—');
        setElText('kpiFastTime', '— s');
        setElText('kpiSpeedup', '—');
    }

    // Hero KPI: Feasibility
    setElText('kpiViolations', `${totalViolations} Capacity Violations`);
    setElText('kpiFeasibleStatus', totalViolations === 0 ? '100% Feasible' : 'Violations Detected');

    // 3. Build Side-by-Side Comparison Metrics Table
    const tbody = document.getElementById('compTableBody');
    if (tbody) {
        tbody.innerHTML = '';
        const keys = ['qpso', 'ga', 'exact'];

        const tableRows = [
            {
                label: 'Optimization Status',
                desc: 'Execution state & feasibility confirmation',
                render: (k) => {
                    const a = algos[k];
                    if (!a) return '<span style="color:#64748b">Not Selected</span>';
                    if (a.error) return `<span class="diff-tag worse" title="${a.error}">Skipped</span>`;
                    if (a.violations === 0) return '<span class="diff-tag better">Optimal Feasible (0 Violations)</span>';
                    return `<span class="diff-tag worse">${a.violations} Violations</span>`;
                }
            },
            {
                label: 'Total Fleet Distance (km)',
                desc: 'Combined distance travelled across all vehicle routes',
                isBestMin: true,
                valFn: (k) => (algos[k] && algos[k].distance_km > 0) ? algos[k].distance_km : null,
                render: (k) => {
                    const a = algos[k];
                    if (!a || a.distance_km <= 0) return a && a.error ? '—' : '<span style="color:#64748b">—</span>';
                    let diffTag = '';
                    if (gaDist && k !== 'ga') {
                        const diffPct = ((a.distance_km - gaDist) / gaDist * 100);
                        if (diffPct < 0) {
                            diffTag = `<span class="diff-tag better">${diffPct.toFixed(1)}% vs GA</span>`;
                        } else if (diffPct > 0) {
                            diffTag = `<span class="diff-tag worse">+${diffPct.toFixed(1)}% vs GA</span>`;
                        }
                    }
                    return `<b>${a.distance_km.toFixed(2)} km</b> ${diffTag}`;
                }
            },
            {
                label: 'Total Travel Time (hrs)',
                desc: 'Aggregate driving time across full fleet',
                isBestMin: true,
                valFn: (k) => (algos[k] && algos[k].time_sec > 0) ? algos[k].time_sec : null,
                render: (k) => {
                    const a = algos[k];
                    if (!a || a.time_sec <= 0) return '—';
                    const hrs = (a.time_sec / 3600).toFixed(2);
                    const mins = Math.round(a.time_sec / 60);
                    return `<b>${hrs} hrs</b> <span style="font-size:11px; color:#94a3b8;">(${mins} mins)</span>`;
                }
            },
            {
                label: 'Optimization Runtime (sec)',
                desc: 'Time taken to compute the routing schedule',
                isFastestMin: true,
                valFn: (k) => (algos[k] && algos[k].runtime_sec !== undefined) ? algos[k].runtime_sec : null,
                render: (k) => {
                    const a = algos[k];
                    if (!a || a.runtime_sec === undefined) return '—';
                    let speedupTag = '';
                    if (algos.exact && algos.exact.runtime_sec > 0 && k !== 'exact') {
                        const speed = (algos.exact.runtime_sec / Math.max(0.001, a.runtime_sec)).toFixed(1);
                        speedupTag = `<span class="diff-tag better">${speed}x Speedup</span>`;
                    }
                    return `<b>${a.runtime_sec.toFixed(3)}s</b> ${speedupTag}`;
                }
            },
            {
                label: 'Capacity Violations',
                desc: 'Over-capacity load allocations (0 is strictly required)',
                render: (k) => {
                    const a = algos[k];
                    if (!a || a.distance_km <= 0) return '—';
                    if (a.violations === 0) return '<b style="color:#10b981;">0 (Strictly Feasible)</b>';
                    return `<b style="color:#ef4444;">${a.violations} Overloaded</b>`;
                }
            },
            {
                label: 'Active Vehicles Deployed',
                desc: 'Number of vehicles utilized out of available fleet',
                render: (k) => {
                    const a = algos[k];
                    if (!a || !a.route_metrics) return '—';
                    const count = a.route_metrics.length;
                    return `<b>${count} of ${config.num_vehicles || '—'} vehicles</b>`;
                }
            },
            {
                label: 'Average Route Distance',
                desc: 'Mean km travelled per dispatched vehicle',
                render: (k) => {
                    const a = algos[k];
                    if (!a || !a.route_metrics || a.route_metrics.length === 0) return '—';
                    const avg = (a.distance_km / a.route_metrics.length).toFixed(2);
                    return `<b>${avg} km</b>`;
                }
            },
            {
                label: 'Longest Route (Max Distance)',
                desc: 'Distance and stops of the longest single vehicle route',
                render: (k) => {
                    const a = algos[k];
                    if (!a || !a.route_metrics || a.route_metrics.length === 0) return '—';
                    const maxRoute = a.route_metrics.reduce((prev, curr) => (curr.distance_km > prev.distance_km) ? curr : prev, a.route_metrics[0]);
                    return `<b>${maxRoute.distance_km} km</b> <span style="font-size:11px; color:#94a3b8;">(${maxRoute.stops} stops, ${maxRoute.load} units)</span>`;
                }
            },
            {
                label: 'Average Capacity Utilization',
                desc: 'Mean percentage of cargo volume filled across fleet',
                render: (k) => {
                    const a = algos[k];
                    if (!a || !a.route_metrics || a.route_metrics.length === 0) return '—';
                    const avgUtil = (a.route_metrics.reduce((acc, m) => acc + (m.utilization_pct || 0), 0) / a.route_metrics.length).toFixed(1);
                    return `<b>${avgUtil}%</b>`;
                }
            },
            {
                label: 'Convergence Iterations',
                desc: 'Total evolutionary epochs or solver iterations',
                render: (k) => {
                    const a = algos[k];
                    if (!a) return '—';
                    if (k === 'qpso') return '<b>50 Iterations</b> (Quantum Delta-Well)';
                    if (k === 'ga') return '<b>50 Generations</b> (Elitist GA)';
                    if (k === 'exact') return (a.distance_km > 0) ? '<b>Guided Local Search</b> (15s Bound)' : '—';
                    return '—';
                }
            },
            {
                label: 'Algorithmic Paradigm',
                desc: 'Mathematical and optimization methodology',
                render: (k) => {
                    if (k === 'qpso') return '<span style="color:#10b981; font-weight:600;">Quantum-Inspired Metaheuristic</span><br><span style="font-size:11px; color:#64748b;">Bloch Sphere Encoding + Delta Potential Well</span>';
                    if (k === 'ga') return '<span style="color:#ef4444; font-weight:600;">Classical Metaheuristic</span><br><span style="font-size:11px; color:#64748b;">Angular Sweep Clustering + Genetic TSP</span>';
                    if (k === 'exact') return '<span style="color:#f59e0b; font-weight:600;">Exact / Math Programming</span><br><span style="font-size:11px; color:#64748b;">Google OR-Tools Guided Local Search</span>';
                    return '—';
                }
            }
        ];

        tableRows.forEach(row => {
            const tr = document.createElement('tr');
            let html = `
                <td class="metric-name">
                    <div>${row.label}</div>
                    <div style="font-size:11px; color:#64748b; font-weight:400; margin-top:2px;">${row.desc}</div>
                </td>
            `;

            let minVal = Infinity, minKey = null;
            if (row.isBestMin || row.isFastestMin) {
                keys.forEach(k => {
                    const v = row.valFn ? row.valFn(k) : null;
                    if (v !== null && v < minVal) {
                        minVal = v;
                        minKey = k;
                    }
                });
            }

            keys.forEach(k => {
                const isBest = (minKey !== null && k === minKey);
                const cellClass = isBest ? (row.isFastestMin ? 'best-cell-fast' : 'best-cell') : '';
                const content = row.render(k, isBest);
                html += `<td class="${cellClass}">${content}</td>`;
            });

            tr.innerHTML = html;
            tbody.appendChild(tr);
        });
    }

    // 4. Render Big Convergence Chart
    renderBigConvergenceChart(algos);

    // 5. Render Fleet Workload Distribution
    renderFleetDistribution(data);

    // 6. Render Route Manifests
    // Default to the algorithm with lowest distance or first available
    const manifestAlgo = bestDistAlgo || activeManifestAlgo || 'exact';
    showManifest(manifestAlgo);
}

// ---- Render Big Convergence Chart in Comparison View ----
function renderBigConvergenceChart(algorithms) {
    const canvas = document.getElementById('bigChartCanvas');
    if (!canvas) return;
    if (bigConvergenceChart) bigConvergenceChart.destroy();

    const datasets = [];
    Object.keys(algorithms || {}).forEach(key => {
        const algo = algorithms[key];
        if (!algo || !algo.convergence || algo.convergence.length === 0) return;
        datasets.push({
            label: ALGO_NAMES[key] || key,
            data: algo.convergence,
            borderColor: ALGO_COLORS[key],
            backgroundColor: ALGO_COLORS[key] + '18',
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointRadius: 2,
            pointHoverRadius: 5
        });
    });

    if (datasets.length === 0) return;

    bigConvergenceChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: datasets[0].data.map((_, i) => `Iter ${i + 1}`),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#cbd5e1', font: { family: 'Inter', size: 12, weight: 600 } }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} km`
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Optimization Iteration / Generation', color: '#94a3b8', font: { size: 12 } },
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(99,102,241,0.06)' }
                },
                y: {
                    title: { display: true, text: 'Total Fleet Distance (km)', color: '#94a3b8', font: { size: 12 } },
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(99,102,241,0.06)' }
                }
            }
        }
    });
}

// ---- Render Fleet Workload Distribution ----
function renderFleetDistribution(data) {
    const listEl = document.getElementById('fleetDistributionList');
    if (!listEl) return;

    const algos = data.algorithms || {};
    // Use best algorithm or first available
    let targetAlgo = algos.exact || algos.qpso || algos.ga || null;

    if (!targetAlgo || !targetAlgo.route_metrics || targetAlgo.route_metrics.length === 0) {
        listEl.innerHTML = '<div class="empty-state">No route details available for workload balancing.</div>';
        return;
    }

    listEl.innerHTML = '';
    const cap = (data.config && data.config.capacity) ? data.config.capacity : 40;

    targetAlgo.route_metrics.forEach(m => {
        const item = document.createElement('div');
        item.className = 'fleet-bar-item';
        item.innerHTML = `
            <div class="fleet-bar-header">
                <span>Vehicle #${m.vehicle_id} <span style="font-size:10px; color:#64748b;">(${m.stops} stops)</span></span>
                <span class="val">${m.distance_km} km • ${m.load}/${cap} cap (${m.utilization_pct}%)</span>
            </div>
            <div class="fleet-bar-track">
                <div class="fleet-bar-fill" style="width:${Math.min(100, m.utilization_pct)}%;"></div>
            </div>
        `;
        listEl.appendChild(item);
    });
}

// ---- Show Route Manifest for an Algorithm ----
function showManifest(algoKey) {
    activeManifestAlgo = algoKey;

    // Update pill tabs
    document.querySelectorAll('#routeManifestTabs .pill-tab').forEach(b => {
        b.classList.toggle('active', b.dataset.algo === algoKey);
    });

    const contentEl = document.getElementById('routeManifestContent');
    if (!contentEl) return;

    if (!latestSimulationData || !latestSimulationData.algorithms || !latestSimulationData.algorithms[algoKey]) {
        contentEl.innerHTML = `<div class="empty-state">${ALGO_NAMES[algoKey] || algoKey} was not selected in the latest simulation run.</div>`;
        return;
    }

    const algo = latestSimulationData.algorithms[algoKey];
    if (algo.error) {
        contentEl.innerHTML = `<div class="empty-state" style="color:#f87171;">⚠️ ${algo.error}</div>`;
        return;
    }

    if (!algo.route_metrics || algo.route_metrics.length === 0) {
        contentEl.innerHTML = `<div class="empty-state">No vehicle routes found.</div>`;
        return;
    }

    let html = '<div class="manifest-grid">';
    algo.route_metrics.forEach(m => {
        const stopsStr = m.sequence.length > 0 ? `Depot → ` + m.sequence.map(s => `#${s}`).join(' → ') + ` → Depot` : 'Empty';
        html += `
            <div class="manifest-item">
                <div class="manifest-item-header">
                    <span>🚛 Vehicle #${m.vehicle_id}</span>
                    <span class="manifest-badge">${m.distance_km} km</span>
                </div>
                <div class="manifest-metrics">
                    <span>Stops: <b>${m.stops}</b></span>
                    <span>Payload: <b>${m.load} / ${m.capacity}</b></span>
                    <span>Util: <b>${m.utilization_pct}%</b></span>
                    <span>Time: <b>${m.time_min}m</b></span>
                </div>
                <div class="manifest-path" title="${stopsStr}">${stopsStr}</div>
            </div>
        `;
    });
    html += '</div>';
    contentEl.innerHTML = html;
}

// ---- Quick Convergence Chart in Map HUD ----
function renderConvergenceChart(algorithms) {
    const canvas = document.getElementById('chartCanvas');
    if (!canvas) return;
    if (convergenceChart) convergenceChart.destroy();

    const datasets = [];
    Object.keys(algorithms || {}).forEach(key => {
        const algo = algorithms[key];
        if (!algo || !algo.convergence || algo.convergence.length === 0) return;
        datasets.push({
            label: ALGO_NAMES[key] ? ALGO_NAMES[key].split(' ')[0] : key,
            data: algo.convergence,
            borderColor: ALGO_COLORS[key],
            backgroundColor: ALGO_COLORS[key] + '20',
            borderWidth: 2,
            fill: true,
            tension: 0.4,
            pointRadius: 0
        });
    });

    const chartContainer = document.getElementById('convergenceChart');
    if (datasets.length === 0) {
        if (chartContainer) chartContainer.style.display = 'none';
        return;
    }
    if (chartContainer) chartContainer.style.display = 'block';

    convergenceChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: datasets[0].data.map((_, i) => i + 1),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 } } }
            },
            scales: {
                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(99,102,241,0.06)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(99,102,241,0.06)' } }
            }
        }
    });
}

// ---- Utility: Copy Markdown Comparison Table ----
function copyTableMarkdown() {
    if (!latestSimulationData) {
        alert('Please run a simulation first to generate comparison metrics.');
        return;
    }

    const algos = latestSimulationData.algorithms || {};
    const q = algos.qpso || {};
    const g = algos.ga || {};
    const e = algos.exact || {};

    const md = [
        `### Multi-Algorithm VRP Optimization Benchmark Results`,
        `| Metric | Delta-Well QPSO (Quantum) | Classical Heuristic GA | Exact Solver (OR-Tools) |`,
        `| :--- | :--- | :--- | :--- |`,
        `| **Fleet Distance (km)** | ${q.distance_km ? q.distance_km + ' km' : '—'} | ${g.distance_km ? g.distance_km + ' km' : '—'} | ${e.distance_km && e.distance_km > 0 ? e.distance_km + ' km' : (e.error || '—')} |`,
        `| **Travel Time (hrs)** | ${q.time_sec ? (q.time_sec/3600).toFixed(2) + 'h' : '—'} | ${g.time_sec ? (g.time_sec/3600).toFixed(2) + 'h' : '—'} | ${e.time_sec && e.time_sec > 0 ? (e.time_sec/3600).toFixed(2) + 'h' : '—'} |`,
        `| **Runtime (sec)** | ${q.runtime_sec !== undefined ? q.runtime_sec.toFixed(3) + 's' : '—'} | ${g.runtime_sec !== undefined ? g.runtime_sec.toFixed(3) + 's' : '—'} | ${e.runtime_sec !== undefined ? e.runtime_sec.toFixed(3) + 's' : '—'} |`,
        `| **Constraint Violations** | ${q.violations !== undefined ? q.violations : '—'} | ${g.violations !== undefined ? g.violations : '—'} | ${e.violations !== undefined ? e.violations : '—'} |`,
        `| **Active Vehicles** | ${q.route_metrics ? q.route_metrics.length : '—'} | ${g.route_metrics ? g.route_metrics.length : '—'} | ${e.route_metrics ? e.route_metrics.length : '—'} |`
    ].join('\n');

    navigator.clipboard.writeText(md).then(() => {
        alert('✅ Markdown comparison table copied to clipboard!');
    }).catch(() => {
        alert('Could not copy to clipboard. Please copy manually.');
    });
}

// ---- Utility: Export Results JSON ----
function exportResultsJSON() {
    if (!latestSimulationData) {
        alert('Please run a simulation first.');
        return;
    }
    const blob = new Blob([JSON.stringify(latestSimulationData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `quantum_vrp_benchmark_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ---- Helpers ----
function clearMap() {
    if (map) {
        customerMarkers.forEach(m => map.removeLayer(m));
        customerMarkers = [];
        Object.values(routeLayers).forEach(layers => layers.forEach(l => map.removeLayer(l)));
        routeLayers = {};
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ---- Initialize On Page Load ----
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initSliders();
    loadCities();
});
