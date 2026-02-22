/* ── Panel toggle (mobile) ──────────────────────────── */

const panelToggle = document.getElementById("panel-toggle");
const infoPanel = document.getElementById("info-panel");

panelToggle.addEventListener("click", () => {
    const isOpen = infoPanel.classList.toggle("open");
    panelToggle.textContent = isOpen ? "\u2715" : "\u2630";
});

/* ── PlowMap class ─────────────────────────────────── */

class PlowMap {
    constructor(container, options) {
        this.map = new maplibregl.Map({ container, ...options });
        this.coverageAbort = null;
    }

    on(event, layerOrCb, cb) {
        if (cb) this.map.on(event, layerOrCb, cb);
        else this.map.on(event, layerOrCb);
    }
    addControl(control, position) { this.map.addControl(control, position); }
    getZoom() { return this.map.getZoom(); }
    getCenter() { return this.map.getCenter(); }
    getBounds() { return this.map.getBounds(); }
    getCanvas() { return this.map.getCanvas(); }

    /* ── Vehicles ───────────────────────────────────── */

    initVehicles(data) {
        this.map.addSource("vehicles", { type: "geojson", data });
        this.map.addLayer({
            id: "vehicle-circles",
            type: "circle",
            source: "vehicles",
            paint: {
                "circle-color": [
                    "match", ["get", "vehicle_type"],
                    "SA PLOW TRUCK", "#2563eb",
                    "TA PLOW TRUCK", "#2563eb",
                    "LOADER", "#ea580c",
                    "GRADER", "#16a34a",
                    "#6b7280",
                ],
                "circle-radius": 7,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 2,
            },
        });
    }

    updateVehicles(data) {
        this.map.getSource("vehicles").setData(data);
    }

    setVehiclesVisible(visible) {
        if (this.map.getLayer("vehicle-circles")) {
            this.map.setLayoutProperty(
                "vehicle-circles",
                "visibility",
                visible ? "visible" : "none",
            );
        }
    }

    /* ── Trails ─────────────────────────────────────── */

    showTrail(trailData, lineData) {
        this.clearTrail();
        this.map.addSource("vehicle-trail", { type: "geojson", data: trailData });
        this.map.addSource("vehicle-trail-line", { type: "geojson", data: lineData });

        this.map.addLayer(
            {
                id: "vehicle-trail-line",
                type: "line",
                source: "vehicle-trail-line",
                paint: {
                    "line-color": "#60a5fa",
                    "line-width": 3,
                    "line-opacity": ["get", "seg_opacity"],
                },
            },
            "vehicle-circles",
        );

        this.map.addLayer(
            {
                id: "vehicle-trail-dots",
                type: "circle",
                source: "vehicle-trail",
                paint: {
                    "circle-color": "#60a5fa",
                    "circle-radius": 4,
                    "circle-opacity": ["get", "trail_opacity"],
                    "circle-stroke-color": "#ffffff",
                    "circle-stroke-width": 1,
                    "circle-stroke-opacity": ["*", ["get", "trail_opacity"], 0.8],
                },
            },
            "vehicle-circles",
        );
    }

    updateTrail(trailData, lineData) {
        const trailSource = this.map.getSource("vehicle-trail");
        if (trailSource) trailSource.setData(trailData);

        const lineSource = this.map.getSource("vehicle-trail-line");
        if (lineSource) lineSource.setData(lineData);
    }

    clearTrail() {
        if (this.map.getLayer("vehicle-trail-dots"))
            this.map.removeLayer("vehicle-trail-dots");
        if (this.map.getLayer("vehicle-trail-line"))
            this.map.removeLayer("vehicle-trail-line");
        if (this.map.getSource("vehicle-trail"))
            this.map.removeSource("vehicle-trail");
        if (this.map.getSource("vehicle-trail-line"))
            this.map.removeSource("vehicle-trail-line");
    }

    /* ── Coverage ───────────────────────────────────── */

    renderCoverageLines(segmentData) {
        const source = this.map.getSource("coverage-lines");
        if (source) {
            source.setData(segmentData);
        } else {
            this.map.addSource("coverage-lines", { type: "geojson", data: segmentData });
            this.map.addLayer({
                id: "coverage-lines",
                type: "line",
                source: "coverage-lines",
                paint: {
                    "line-color": ["get", "seg_color"],
                    "line-width": 3,
                    "line-opacity": ["get", "seg_opacity"],
                },
            });
        }
    }

    renderHeatmap(pointData) {
        const source = this.map.getSource("coverage-heatmap");
        if (source) {
            source.setData(pointData);
        } else {
            this.map.addSource("coverage-heatmap", { type: "geojson", data: pointData });
            this.map.addLayer({
                id: "coverage-heatmap",
                type: "heatmap",
                source: "coverage-heatmap",
                paint: {
                    "heatmap-weight": 0.5,
                    "heatmap-intensity": [
                        "interpolate", ["linear"], ["zoom"],
                        10, 0.5, 12, 1, 15, 2,
                    ],
                    "heatmap-radius": [
                        "interpolate", ["linear"], ["zoom"],
                        10, 3, 12, 8, 14, 15, 16, 25,
                    ],
                    "heatmap-opacity": 0.75,
                    "heatmap-color": [
                        "interpolate", ["linear"], ["heatmap-density"],
                        0, "rgba(0,0,0,0)",
                        0.15, "#2563eb",
                        0.35, "#60a5fa",
                        0.55, "#fbbf24",
                        0.75, "#f97316",
                        1.0, "#ef4444",
                    ],
                },
            });
        }
    }

    setCoverageLineVisibility(visible) {
        if (this.map.getLayer("coverage-lines")) {
            this.map.setLayoutProperty(
                "coverage-lines",
                "visibility",
                visible ? "visible" : "none",
            );
        }
    }

    setHeatmapVisibility(visible) {
        if (this.map.getLayer("coverage-heatmap")) {
            this.map.setLayoutProperty(
                "coverage-heatmap",
                "visibility",
                visible ? "visible" : "none",
            );
        }
    }

    clearCoverage() {
        if (this.map.getLayer("coverage-lines"))
            this.map.removeLayer("coverage-lines");
        if (this.map.getSource("coverage-lines"))
            this.map.removeSource("coverage-lines");
        if (this.map.getLayer("coverage-heatmap"))
            this.map.removeLayer("coverage-heatmap");
        if (this.map.getSource("coverage-heatmap"))
            this.map.removeSource("coverage-heatmap");
    }

    /* ── Abort management ───────────────────────────── */

    abortCoverage() {
        if (this.coverageAbort) {
            this.coverageAbort.abort();
            this.coverageAbort = null;
        }
    }

    newCoverageSignal() {
        this.abortCoverage();
        this.coverageAbort = new AbortController();
        return this.coverageAbort.signal;
    }
}

/* ── Map init ──────────────────────────────────────── */

const plowMap = new PlowMap("map", {
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [-52.71, 47.56],
    zoom: 12,
});

const geolocate = new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: true,
    showUserHeading: true,
});
plowMap.addControl(geolocate, "bottom-right");
geolocate.on("geolocate", () => gtag("event", "geolocate"));

/* ── Analytics: debounced viewport tracking ────────── */

let viewportTimer = null;

plowMap.on("moveend", () => {
    clearTimeout(viewportTimer);
    viewportTimer = setTimeout(() => {
        const zoom = plowMap.getZoom();
        if (zoom < 13) return;

        const center = plowMap.getCenter();
        const bounds = plowMap.getBounds();
        const round4 = (n) => Math.round(n * 10000) / 10000;

        gtag("event", "viewport_focus", {
            zoom: Math.round(zoom * 10) / 10,
            center_lng: round4(center.lng),
            center_lat: round4(center.lat),
        });

        const payload = JSON.stringify({
            zoom: Math.round(zoom * 10) / 10,
            center: [round4(center.lng), round4(center.lat)],
            bounds: {
                sw: [round4(bounds.getWest()), round4(bounds.getSouth())],
                ne: [round4(bounds.getEast()), round4(bounds.getNorth())],
            },
        });

        if (navigator.sendBeacon) {
            navigator.sendBeacon(
                "/track",
                new Blob([payload], { type: "application/json" }),
            );
        } else {
            fetch("/track", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: payload,
                keepalive: true,
            }).catch(() => {});
        }
    }, 5000);
});

/* ── Utilities ─────────────────────────────────────── */

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

const VEHICLE_COLORS = {
    "SA PLOW TRUCK": "#2563eb",
    "TA PLOW TRUCK": "#2563eb",
    LOADER: "#ea580c",
    GRADER: "#16a34a",
};
const DEFAULT_COLOR = "#6b7280";

function vehicleColor(type) {
    return VEHICLE_COLORS[type] || DEFAULT_COLOR;
}

function formatTimestamp(ts) {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function formatBytes(bytes) {
    if (bytes === null || bytes === undefined) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024)
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

/* ── API ───────────────────────────────────────────── */

async function fetchVehicles() {
    const resp = await fetch("/vehicles");
    return resp.json();
}

function updateVehicleCount(data) {
    const count = data.features ? data.features.length : 0;
    document.getElementById("vehicle-count").textContent =
        count + " vehicle" + (count !== 1 ? "s" : "") + " tracked";
    fetch("/stats")
        .then((r) => r.json())
        .then((stats) => {
            if (stats.db_size_bytes) {
                document.getElementById("db-size").textContent =
                    formatBytes(stats.db_size_bytes) + " of data";
            }
        })
        .catch(() => {});
}

function filterRecentFeatures(data) {
    const cutoff = Date.now() - ONE_DAY_MS;
    return {
        ...data,
        features: data.features.filter(
            (f) => new Date(f.properties.timestamp).getTime() > cutoff,
        ),
    };
}

/* ── Vehicle detail panel: DOM refs ─────────────────── */

const detailPanel = document.getElementById("vehicle-detail");
const detailName = document.getElementById("detail-name");
const detailType = document.getElementById("detail-type");
const detailSpeed = document.getElementById("detail-speed");
const detailBearing = document.getElementById("detail-bearing");
const detailUpdated = document.getElementById("detail-updated");

/* ── Vehicle trails ────────────────────────────────── */

async function fetchTrail(vehicleId, vehicleTimestamp) {
    let until, since;
    if (vehicleTimestamp) {
        until = new Date(vehicleTimestamp);
        since = new Date(until.getTime() - 10 * 60 * 1000);
    } else {
        until = new Date();
        since = new Date(until.getTime() - 10 * 60 * 1000);
    }
    const resp = await fetch(
        `/vehicles/${vehicleId}/history?since=${since.toISOString()}&until=${until.toISOString()}&limit=2000`,
    );
    return resp.json();
}

function addTrailOpacity(features) {
    const count = features.length;
    return features.map((f, i) => ({
        ...f,
        properties: {
            ...f.properties,
            trail_opacity: count === 1 ? 0.7 : 0.15 + (i / (count - 1)) * 0.55,
        },
    }));
}

function buildTrailSegments(features) {
    const segments = [];
    for (let i = 0; i < features.length - 1; i++) {
        segments.push({
            type: "Feature",
            geometry: {
                type: "LineString",
                coordinates: [
                    features[i].geometry.coordinates,
                    features[i + 1].geometry.coordinates,
                ],
            },
            properties: { seg_opacity: features[i].properties.trail_opacity },
        });
    }
    return segments;
}

/* ── Coverage: DOM refs ────────────────────────────── */

const btnRealtime = document.getElementById("btn-realtime");
const btnCoverage = document.getElementById("btn-coverage");
const coveragePanelEl = document.getElementById("coverage-panel");
const timeSlider = document.getElementById("time-slider");
const sliderLabel = document.getElementById("slider-label");
const coverageLoading = document.getElementById("coverage-loading");
const coverageRangeLabel = document.getElementById("coverage-range-label");
const datePickerRow = document.getElementById("date-picker-row");
const coverageDateInput = document.getElementById("coverage-date");
const timeRangePresets = document.getElementById("time-range-presets");
const btnLines = document.getElementById("btn-lines");
const btnHeatmap = document.getElementById("btn-heatmap");

/* ── Stateless DOM helpers ─────────────────────────── */

function formatRangeDate(d) {
    return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function setPresetActive(value) {
    timeRangePresets
        .querySelectorAll("button")
        .forEach((btn) =>
            btn.classList.toggle("active", btn.dataset.hours === value),
        );
    datePickerRow.classList.toggle("visible", value === "date");
}

function showLegend(type) {
    document.getElementById("legend-vehicles").style.display =
        type === "vehicles" ? "" : "none";
    document.getElementById("legend-heatmap").style.display =
        type === "heatmap" ? "" : "none";
}

async function initDatePickerBounds() {
    try {
        const resp = await fetch("/stats");
        const stats = await resp.json();
        if (stats.earliest) {
            coverageDateInput.min = stats.earliest.slice(0, 10);
        }
        coverageDateInput.max = new Date().toISOString().slice(0, 10);
    } catch (e) {
        // ignore
    }
}
initDatePickerBounds();

/* ── Legend toggle (pure UI, no app state) ─────────── */

const legendToggleBtn = document.getElementById("legend-toggle");
const legendBody = document.getElementById("legend-body");
legendToggleBtn.addEventListener("click", () => {
    const collapsed = legendBody.classList.toggle("collapsed");
    legendToggleBtn.classList.toggle("collapsed", collapsed);
});

/* ── PlowApp class ─────────────────────────────────── */

class PlowApp {
    constructor(plowMap) {
        this.map = plowMap;

        // Mode
        this.mode = "realtime";

        // Realtime
        this.refreshInterval = null;
        this.activeVehicleId = null;
        this.activeVehicleTimestamp = null;

        // Coverage
        this.coverageData = null;
        this.coverageSince = null;
        this.coverageUntil = null;
        this.coveragePreset = "24";
        this.coverageView = "lines";
    }

    /* ── Mode switching ────────────────────────────── */

    async switchMode(mode) {
        if (mode === this.mode) return;
        gtag("event", "mode_switch", { mode });
        this.mode = mode;
        btnRealtime.classList.toggle("active", mode === "realtime");
        btnCoverage.classList.toggle("active", mode === "coverage");
        if (mode === "realtime") {
            this.enterRealtime();
        } else {
            await this.enterCoverage();
        }
    }

    enterRealtime() {
        this.map.abortCoverage();
        this.map.clearCoverage();
        coveragePanelEl.style.display = "none";
        this.coverageData = null;
        this.map.setVehiclesVisible(true);
        document.getElementById("vehicle-count").style.display = "";
        document.getElementById("db-size").style.display = "";
        showLegend("vehicles");
        this.startAutoRefresh();
    }

    async enterCoverage() {
        this.stopAutoRefresh();
        this.closeDetail();
        this.coverageView = "lines";
        btnLines.classList.add("active");
        btnHeatmap.classList.remove("active");
        showLegend("vehicles");
        this.map.setVehiclesVisible(false);
        document.getElementById("vehicle-count").style.display = "none";
        document.getElementById("db-size").style.display = "none";
        coveragePanelEl.style.display = "block";

        this.coveragePreset = "24";
        setPresetActive("24");
        const now = new Date();
        await this.loadCoverageForRange(new Date(now.getTime() - ONE_DAY_MS), now);
    }

    /* ── Coverage ──────────────────────────────────── */

    async loadCoverageForRange(since, until) {
        const signal = this.map.newCoverageSignal();

        this.coverageSince = since;
        this.coverageUntil = until;
        this.updateRangeLabel();
        coverageLoading.style.display = "block";
        timeSlider.value = 1000;
        this.map.clearCoverage();
        try {
            const resp = await fetch(
                `/coverage?since=${since.toISOString()}&until=${until.toISOString()}`,
                { signal },
            );
            this.coverageData = await resp.json();
        } catch (err) {
            if (err.name === "AbortError") return;
            throw err;
        }
        coverageLoading.style.display = "none";
        this.renderCoverage(1000);
    }

    async loadCoverageForDate(dateStr) {
        const start = new Date(dateStr + "T00:00:00");
        const end = new Date(dateStr + "T23:59:59");
        await this.loadCoverageForRange(start, end);
    }

    switchCoverageView(view) {
        if (view === this.coverageView) return;
        gtag("event", "coverage_view", { view });
        this.coverageView = view;
        btnLines.classList.toggle("active", view === "lines");
        btnHeatmap.classList.toggle("active", view === "heatmap");
        showLegend(view === "heatmap" ? "heatmap" : "vehicles");
        this.renderCoverage(parseInt(timeSlider.value));
    }

    renderCoverage(sliderVal) {
        if (!this.coverageData || this.mode !== "coverage") return;
        const cutoff = this.sliderToTime(sliderVal);
        sliderLabel.textContent = formatTimestamp(cutoff.toISOString());

        if (this.coverageView === "lines") {
            this.map.setHeatmapVisibility(false);
            this.renderCoverageLines(sliderVal, cutoff);
            this.map.setCoverageLineVisibility(true);
        } else {
            this.map.setCoverageLineVisibility(false);
            this.renderHeatmap(sliderVal);
            this.map.setHeatmapVisibility(true);
        }
    }

    renderCoverageLines(sliderVal, cutoff) {
        const sinceMs = this.coverageSince.getTime();
        const rangeMs = cutoff.getTime() - sinceMs;

        const segmentFeatures = [];
        for (const feature of this.coverageData.features) {
            const coords = feature.geometry.coordinates;
            const timestamps = feature.properties.timestamps;
            const color = vehicleColor(feature.properties.vehicle_type);

            for (let i = 0; i < coords.length - 1; i++) {
                const tMs = new Date(timestamps[i]).getTime();
                const tNextMs = new Date(timestamps[i + 1]).getTime();
                if (tNextMs > cutoff.getTime()) break;

                const progress = rangeMs > 0 ? (tMs - sinceMs) / rangeMs : 1;
                const opacity = 0.15 + progress * 0.65;

                segmentFeatures.push({
                    type: "Feature",
                    geometry: {
                        type: "LineString",
                        coordinates: [coords[i], coords[i + 1]],
                    },
                    properties: { seg_opacity: opacity, seg_color: color },
                });
            }
        }

        const data = { type: "FeatureCollection", features: segmentFeatures };
        this.map.renderCoverageLines(data);
    }

    renderHeatmap(sliderVal) {
        if (!this.coverageData) return;
        const cutoff = this.sliderToTime(sliderVal);

        const pointFeatures = [];
        for (const feature of this.coverageData.features) {
            const coords = feature.geometry.coordinates;
            const timestamps = feature.properties.timestamps;
            for (let i = 0; i < coords.length; i++) {
                const tMs = new Date(timestamps[i]).getTime();
                if (tMs > cutoff.getTime()) break;
                pointFeatures.push({
                    type: "Feature",
                    geometry: { type: "Point", coordinates: coords[i] },
                    properties: {},
                });
            }
        }

        const data = { type: "FeatureCollection", features: pointFeatures };
        this.map.renderHeatmap(data);
    }

    sliderToTime(val) {
        const range = this.coverageUntil.getTime() - this.coverageSince.getTime();
        return new Date(this.coverageSince.getTime() + (val / 1000) * range);
    }

    updateRangeLabel() {
        if (this.coverageSince && this.coverageUntil) {
            coverageRangeLabel.textContent =
                formatRangeDate(this.coverageSince) +
                " \u2192 " +
                formatRangeDate(this.coverageUntil);
        }
    }

    /* ── Auto-refresh ──────────────────────────────── */

    startAutoRefresh() {
        if (this.refreshInterval) return;
        this.refreshInterval = setInterval(async () => {
            if (this.mode !== "realtime") return;
            try {
                const rawData = await fetchVehicles();
                const freshData = filterRecentFeatures(rawData);
                this.map.updateVehicles(freshData);
                updateVehicleCount(freshData);
                this.updateDetailFromData(freshData);
                this.refreshTrail();
            } catch (err) {
                console.error("Failed to refresh vehicles:", err);
            }
        }, 6000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /* ── Vehicle detail ────────────────────────────── */

    showDetail(p) {
        detailName.textContent = p.description;
        detailType.textContent = p.vehicle_type;
        detailSpeed.textContent = "Speed: " + p.speed + " km/h";
        detailBearing.textContent = "Bearing: " + p.bearing + "\u00B0";
        detailUpdated.textContent = "Updated: " + formatTimestamp(p.timestamp);
        detailPanel.style.display = "block";
    }

    closeDetail() {
        detailPanel.style.display = "none";
        this.activeVehicleId = null;
        this.activeVehicleTimestamp = null;
        this.map.clearTrail();
    }

    updateDetailFromData(data) {
        if (!this.activeVehicleId) return;
        const feature = data.features.find(
            (f) => f.properties.vehicle_id === this.activeVehicleId,
        );
        if (!feature) {
            this.closeDetail();
            return;
        }
        this.activeVehicleTimestamp = feature.properties.timestamp;
        this.showDetail(feature.properties);
    }

    async showTrail(vehicleId, vehicleTimestamp) {
        const data = await fetchTrail(vehicleId, vehicleTimestamp);
        if (!data.features || data.features.length === 0) return;

        const features = addTrailOpacity(data.features);
        const trailData = { type: "FeatureCollection", features };
        const lineData = {
            type: "FeatureCollection",
            features: buildTrailSegments(features),
        };

        this.map.showTrail(trailData, lineData);
    }

    async refreshTrail() {
        if (!this.activeVehicleId) return;
        const data = await fetchTrail(this.activeVehicleId, this.activeVehicleTimestamp);
        if (!data.features || data.features.length === 0) return;

        const features = addTrailOpacity(data.features);

        this.map.updateTrail(
            { type: "FeatureCollection", features },
            { type: "FeatureCollection", features: buildTrailSegments(features) },
        );
    }
}

/* ── App init & event wiring ───────────────────────── */

const app = new PlowApp(plowMap);

// Mode
btnRealtime.addEventListener("click", () => app.switchMode("realtime"));
btnCoverage.addEventListener("click", () => app.switchMode("coverage"));

// Coverage presets
timeRangePresets.addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const value = btn.dataset.hours;
    gtag("event", "coverage_preset", { preset: value });
    app.coveragePreset = value;
    setPresetActive(value);
    if (value === "date") {
        if (coverageDateInput.value) await app.loadCoverageForDate(coverageDateInput.value);
        return;
    }
    const hours = parseInt(value);
    const now = new Date();
    await app.loadCoverageForRange(
        new Date(now.getTime() - hours * 60 * 60 * 1000),
        now,
    );
});

coverageDateInput.addEventListener("change", async () => {
    if (app.coveragePreset === "date" && coverageDateInput.value) {
        gtag("event", "coverage_date_pick", { date: coverageDateInput.value });
        await app.loadCoverageForDate(coverageDateInput.value);
    }
});

// Coverage view
btnLines.addEventListener("click", () => app.switchCoverageView("lines"));
btnHeatmap.addEventListener("click", () => app.switchCoverageView("heatmap"));

// Slider
timeSlider.addEventListener("input", (e) => {
    app.renderCoverage(parseInt(e.target.value));
});

// Detail close
document.getElementById("detail-close").addEventListener("click", () => app.closeDetail());

/* ── Map load: sources, layers, handlers ───────────── */

plowMap.on("load", async () => {
    const rawData = await fetchVehicles();
    const data = filterRecentFeatures(rawData);
    updateVehicleCount(data);

    plowMap.initVehicles(data);

    plowMap.on("mouseenter", "vehicle-circles", () => {
        plowMap.getCanvas().style.cursor = "pointer";
    });
    plowMap.on("mouseleave", "vehicle-circles", () => {
        plowMap.getCanvas().style.cursor = "";
    });

    plowMap.on("click", "vehicle-circles", async (e) => {
        const feature = e.features[0];
        const p = feature.properties;
        gtag("event", "vehicle_click", {
            vehicle_type: p.vehicle_type,
            vehicle_id: p.vehicle_id,
        });

        app.activeVehicleId = p.vehicle_id;
        app.activeVehicleTimestamp = p.timestamp;
        app.showDetail(p);
        await app.showTrail(p.vehicle_id, p.timestamp);
    });

    app.startAutoRefresh();
});
